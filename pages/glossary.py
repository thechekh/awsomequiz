"""AWS Glossary page.

Renders curated entries from data/glossary.json with a search box and an
optional cert filter. Entries are grouped by the first letter of the term
(ignoring the 'Amazon ' / 'AWS ' prefix so EC2 lands under E and S3 under
S, matching how engineers actually look services up).

Available to both anonymous visitors (linked from the Login page) and
signed-in users (sidebar nav). Static content -- @st.cache_data with a
long TTL since data/glossary.json only changes on deploy.
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


@st.cache_data(ttl=3600)
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


st.title("AWS Glossary")

all_entries = _load_entries()
st.caption(
    f"{len(all_entries)} curated terms drawn from the AWS official documentation "
    "and the CLF-C02 / DVA-C02 question banks. Search by service name, alias, "
    "category, or definition text."
)

st.markdown(
    """
    <style>
    .glossary-entry {
        padding: 0.55rem 0.85rem;
        margin-bottom: 0.45rem;
        border-left: 3px solid #2563EB;
        background: rgba(37, 99, 235, 0.04);
        border-radius: 4px;
    }
    .glossary-term {
        font-weight: 600;
        font-size: 1.02rem;
        color: #1E40AF;
    }
    .glossary-meta {
        margin-left: 0.55rem;
        font-size: 0.72rem;
        color: #6B7280;
        white-space: nowrap;
    }
    .glossary-definition {
        margin-top: 0.25rem;
        line-height: 1.45;
        color: #1F2937;
    }
    .glossary-letter {
        font-size: 1.45rem;
        font-weight: 700;
        color: #2563EB;
        margin: 1.1rem 0 0.45rem 0;
        padding-bottom: 0.15rem;
        border-bottom: 1px solid rgba(37, 99, 235, 0.25);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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
    if st.button("Back to sign in / register", use_container_width=False):
        st.switch_page("pages/login.py")
