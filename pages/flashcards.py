"""Anki-style flashcards page.

State machine:
  1. Summary in state    -> show end-of-session summary.
  2. Active study queue  -> render current card (front, then flip to reveal back),
                            user rates "I knew it" / "Need practice", advance.
  3. No state            -> deck picker (list of decks with card counts + progress)
                            and then mode picker for the selected deck.

Card content is HTML (e.g. <b>, <i>, <span style="color: ...">) coming from the
source CSVs. We render via st.markdown(..., unsafe_allow_html=True).
"""

from __future__ import annotations

import streamlit as st

from app.auth import apply_session_to_client, current_user
from app.queries import (
    get_clf_certification,
    get_deck_progress,
    get_flashcard,
    list_flashcard_decks,
    pick_deck_card_ids,
    record_flashcard_review,
)

DECK_KEY = "flashcards_selected_deck"      # dict with id/name/code
QUEUE_KEY = "flashcards_queue"             # list of card UUIDs
INDEX_KEY = "flashcards_index"
FLIPPED_KEY = "flashcards_flipped"         # True = back is showing
SUMMARY_KEY = "flashcards_summary"         # {"knew": N, "practice": M, "deck_name": ...}


def _clear_study_state() -> None:
    for k in (QUEUE_KEY, INDEX_KEY, FLIPPED_KEY):
        st.session_state.pop(k, None)


def _start_session(deck_id: str, deck_name: str, mode: str, count: int | None) -> None:
    queue = pick_deck_card_ids(user["id"], deck_id, mode=mode, count=count)
    if not queue:
        st.warning("No cards match the selected mode.")
        return
    st.session_state[QUEUE_KEY] = queue
    st.session_state[INDEX_KEY] = 0
    st.session_state[FLIPPED_KEY] = False
    st.session_state[DECK_KEY] = {"id": deck_id, "name": deck_name, "mode": mode}
    st.session_state.pop(SUMMARY_KEY, None)
    st.rerun()


user = current_user()
if not user:
    st.switch_page("pages/login.py")
apply_session_to_client()
cert = get_clf_certification()

st.title("Flashcards")

if not cert:
    st.error("Certification not seeded.")
    st.stop()

# ---------------------------------------------------------------------------
# 1. End-of-session summary
# ---------------------------------------------------------------------------

if summary := st.session_state.get(SUMMARY_KEY):
    total = summary["knew"] + summary["practice"]
    if total > 0:
        pct = round(summary["knew"] / total * 100, 1)
    else:
        pct = 0.0
    if summary["practice"] == 0:
        st.success(
            f"Studied **{total}** cards in **{summary['deck_name']}** -- "
            f"knew all of them!"
        )
    else:
        st.info(
            f"Studied **{total}** cards in **{summary['deck_name']}**: "
            f"**{summary['knew']}** known, **{summary['practice']}** need practice ({pct}%)."
        )
    c1, c2, c3 = st.columns(3)
    if summary["practice"] > 0 and c1.button("Study the missed ones", type="primary"):
        # Re-pick "practice" mode on the same deck
        st.session_state.pop(SUMMARY_KEY, None)
        _start_session(summary["deck_id"], summary["deck_name"], "practice", None)
    if c2.button("Pick another deck"):
        st.session_state.pop(SUMMARY_KEY, None)
        st.session_state.pop(DECK_KEY, None)
        st.rerun()
    if c3.button("Back to home"):
        st.session_state.pop(SUMMARY_KEY, None)
        st.switch_page("pages/home.py")
    st.stop()

# ---------------------------------------------------------------------------
# 2. Active study queue
# ---------------------------------------------------------------------------

queue = st.session_state.get(QUEUE_KEY)
if queue is not None:
    deck = st.session_state[DECK_KEY]
    total = len(queue)
    index = st.session_state.get(INDEX_KEY, 0)

    with st.sidebar:
        st.divider()
        st.metric("Card", f"{min(index + 1, total)} / {total}")
        st.caption(f"Deck: **{deck['name']}**")
        if st.button("Quit study session", use_container_width=True, key="flashcards_quit"):
            _clear_study_state()
            st.session_state.pop(DECK_KEY, None)
            st.rerun()

    # Done -> set summary
    if index >= total:
        # Tally from session-state-side counters (set during the run, see below)
        st.session_state[SUMMARY_KEY] = {
            "knew": st.session_state.pop("_flashcards_knew", 0),
            "practice": st.session_state.pop("_flashcards_practice", 0),
            "deck_name": deck["name"],
            "deck_id": deck["id"],
        }
        _clear_study_state()
        st.rerun()

    card = get_flashcard(queue[index])

    with st.container(border=True):
        if card.get("category"):
            st.markdown(
                f"<span class='flashcard-category'>{card['category']}</span>",
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<div class='flashcard-front'>{card['front']}</div>",
            unsafe_allow_html=True,
        )
        flipped = st.session_state.get(FLIPPED_KEY, False)
        if flipped:
            st.divider()
            st.markdown(
                f"<div class='flashcard-back'>{card['back']}</div>",
                unsafe_allow_html=True,
            )

    if not flipped:
        if st.button("Show answer", type="primary", use_container_width=True, key=f"flip_{card['id']}"):
            st.session_state[FLIPPED_KEY] = True
            st.rerun()
    else:
        c_left, c_right = st.columns(2)
        if c_left.button(
            "Need more practice",
            use_container_width=True,
            key=f"again_{card['id']}",
        ):
            record_flashcard_review(user["id"], card["id"], knew_it=False)
            st.session_state["_flashcards_practice"] = st.session_state.get(
                "_flashcards_practice", 0
            ) + 1
            st.session_state[INDEX_KEY] = index + 1
            st.session_state[FLIPPED_KEY] = False
            st.rerun()
        if c_right.button(
            "I knew it",
            type="primary",
            use_container_width=True,
            key=f"knew_{card['id']}",
        ):
            record_flashcard_review(user["id"], card["id"], knew_it=True)
            st.session_state["_flashcards_knew"] = st.session_state.get(
                "_flashcards_knew", 0
            ) + 1
            st.session_state[INDEX_KEY] = index + 1
            st.session_state[FLIPPED_KEY] = False
            st.rerun()
    st.stop()

# ---------------------------------------------------------------------------
# 3. Deck + mode picker
# ---------------------------------------------------------------------------

selected = st.session_state.get(DECK_KEY)

if selected is None:
    decks = list_flashcard_decks(cert["id"])
    if not decks:
        st.info(
            "No flashcard decks loaded yet. Run "
            "`uv run python scripts/load_flashcards.py` "
            "(or `.\\dev.ps1 load-flashcards`) to import the CSVs in `questions/`."
        )
        st.stop()

    st.caption("Pick a deck to start studying.")
    for deck in decks:
        progress = get_deck_progress(user["id"], deck["id"])
        with st.container(border=True):
            c_meta, c_btn = st.columns([5, 1])
            with c_meta:
                st.markdown(f"### {deck['name']}")
                if deck.get("description"):
                    st.caption(deck["description"])
                if progress["total"] > 0:
                    reviewed_pct = round(progress["reviewed"] / progress["total"] * 100)
                    known_pct = round(progress["known"] / progress["total"] * 100)
                    st.caption(
                        f"{deck['card_count']} cards  |  "
                        f"reviewed {progress['reviewed']}/{progress['total']} ({reviewed_pct}%)  |  "
                        f"known {progress['known']}/{progress['total']} ({known_pct}%)"
                    )
                else:
                    st.caption(f"{deck['card_count']} cards")
            with c_btn:
                if st.button(
                    "Study",
                    key=f"select_deck_{deck['id']}",
                    type="primary",
                    use_container_width=True,
                ):
                    st.session_state[DECK_KEY] = {
                        "id": deck["id"],
                        "name": deck["name"],
                        "code": deck["code"],
                    }
                    st.rerun()
    st.stop()

# Mode picker for the chosen deck
st.subheader(selected["name"])
if st.button("Pick a different deck"):
    st.session_state.pop(DECK_KEY, None)
    st.rerun()

progress = get_deck_progress(user["id"], selected["id"])
st.caption(
    f"{progress['total']} cards  |  reviewed {progress['reviewed']}  |  known {progress['known']}"
)

mode_label_to_key = {
    "All cards (random order)": "all",
    "Only ones I've never seen": "unseen",
    "Only ones I need to practice": "practice",
}

with st.form("flashcard_mode_picker"):
    mode_label = st.radio("Mode", options=list(mode_label_to_key.keys()))
    count_choice = st.radio(
        "How many",
        options=[10, 25, 50, "All"],
        horizontal=True,
        index=0,
    )
    start = st.form_submit_button("Start studying", type="primary", use_container_width=True)
if start:
    mode = mode_label_to_key[mode_label]
    count = None if count_choice == "All" else int(count_choice)
    _start_session(selected["id"], selected["name"], mode, count)
