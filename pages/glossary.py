"""AWS Glossary page.

Renders curated entries from data/glossary.json with a search box and an
optional cert filter. Entries are grouped by the first letter of the term
(ignoring the 'Amazon ' / 'AWS ' prefix so EC2 lands under E and S3 under
S, matching how engineers actually look services up).

Available to both anonymous visitors (linked from the Login page) and
signed-in users (sidebar nav). Static content -- @st.cache_data with a
moderate TTL; data/glossary.json only changes on deploy, but we keep the
TTL short enough that an expansion lands without a hard container restart.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import streamlit as st

from app.auth import current_user

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "glossary.json"
_PREFIX_RE = re.compile(r"^(Amazon|AWS)\s+", re.IGNORECASE)


@st.cache_data(ttl=300)
def _load_entries() -> list[dict]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return raw["entries"]


def _strip_prefix(term: str) -> str:
    return _PREFIX_RE.sub("", term, count=1)


def _sort_key(term: str) -> tuple[int, str]:
    """Ignore 'Amazon '/'AWS ' prefixes so DynamoDB sorts under D, not A."""
    stripped = _strip_prefix(term)
    return (0 if stripped[:1].isalpha() else 1, stripped.lower())


def _first_letter(term: str) -> str:
    s = _strip_prefix(term)
    return s[:1].upper() if s and s[0].isalpha() else "#"


def _matches(entry: dict, query: str) -> bool:
    if not query:
        return True
    q = query.lower()
    if q in entry["term"].lower():
        return True
    if any(q in a.lower() for a in entry.get("aliases", [])):
        return True
    if q in entry.get("definition", "").lower():
        return True
    if q in entry.get("category", "").lower():
        return True
    return False


# Native page scroll for this very long page. Streamlit puts the scroll on an
# inner [data-testid="stMain"] overflow container that sits *under* the absolute
# stHeader, so on the deployed app the page felt "stuck" at the top and the
# scrollbar only appeared mid-scroll. Relaxing the height/overflow on the app
# containers hands scrolling back to the document (default browser scroll) and
# pinning the header (sticky) keeps it from overlapping the content. Scoped to
# this page -- the markdown is gone once you navigate away.
st.markdown(
    """
    <style>
    /* The un-testid'd wrapper that directly holds stMain also caps height to
       the viewport; relax it too (via :has) so scrolling lands on the document
       (html), not an inner box -- that makes the scrollbar, PageDown and wheel
       all work like a normal page. */
    [data-testid="stApp"],
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stAppViewContainer"] > div:has(> [data-testid="stMain"]) {
        position: static !important;
        height: auto !important;
        min-height: 0 !important;
        overflow: visible !important;
    }
    [data-testid="stMain"] { min-height: 100vh !important; }
    html, body { height: auto !important; min-height: 100% !important; overflow: visible !important; }
    [data-testid="stHeader"] { position: sticky !important; top: 0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("AWS Glossary")

all_entries = _load_entries()
st.caption(
    f"{len(all_entries)} curated terms drawn from the AWS official documentation "
    "and the CLF-C02 / DVA-C02 question banks. Search by service name, alias, "
    "category, or definition text."
)

# Glossary entry styles now live in app/styles.py (CSS variables); no
# page-level color overrides needed -- they pick up the active theme.

# Filter controls
c1, c2 = st.columns([3, 1])
with c1:
    query = st.text_input(
        "Search",
        placeholder="e.g. lambda, encryption, savings plan, IAM, cold start ...",
        key="glossary_search",
    )
with c2:
    cert_filter = st.selectbox(
        "Certification",
        options=["All certs", "CLF-C02", "DVA-C02"],
        key="glossary_cert_filter",
    )

# Apply filters
entries = all_entries
if cert_filter != "All certs":
    entries = [e for e in entries if cert_filter in (e.get("certs") or [])]
entries = [e for e in entries if _matches(e, query)]

if not entries:
    st.info("No entries match. Try a different keyword or clear the cert filter.")
    st.stop()

st.caption(f"Showing **{len(entries)}** of {len(all_entries)} entries.")

# Group + render alphabetically
by_letter: dict[str, list[dict]] = defaultdict(list)
for e in entries:
    by_letter[_first_letter(e["term"])].append(e)
for letter in by_letter:
    by_letter[letter].sort(key=lambda e: _sort_key(e["term"]))

for letter in sorted(by_letter):
    st.markdown(f'<div class="glossary-letter">{letter}</div>', unsafe_allow_html=True)
    for e in by_letter[letter]:
        meta_bits = []
        if e.get("category"):
            meta_bits.append(e["category"])
        if e.get("certs"):
            meta_bits.append(" / ".join(e["certs"]))
        meta_html = (
            f'<span class="glossary-meta">— {" · ".join(meta_bits)}</span>'
            if meta_bits else ""
        )
        st.markdown(
            f'<div class="glossary-entry">'
            f'<span class="glossary-term">{e["term"]}</span>'
            f"{meta_html}"
            f'<div class="glossary-definition">{e["definition"]}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

st.divider()
st.caption(
    "Definitions follow AWS official documentation language; coverage focuses on "
    "the CLF-C02 and DVA-C02 exam scope. More terms get added as new certifications "
    "are loaded into the question bank."
)

# Back-to-login affordance for anonymous visitors (signed-in users have the
# regular sidebar nav so they don't need this).
if not current_user():
    st.divider()
    if st.button("Back to sign in / register", width="content"):
        st.switch_page("pages/login.py")
