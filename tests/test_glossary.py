"""Validate data/glossary.json shape and content.

These tests don't import any Streamlit/Supabase code -- pure JSON validation
so they're fast and CI-friendly.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "data" / "glossary.json"

ALLOWED_CATEGORIES = {
    "Concepts & Architecture",
    "Security, Identity & Compliance",
    "Management & Monitoring",
    "Compute",
    "Networking & Content Delivery",
    "Database",
    "Developer Tools",
    "Application Integration",
    "Storage",
    "Billing & Pricing",
    "Machine Learning",
    "Analytics",
    "Migration & Transfer",
    "Business Applications",
    "Containers",
    "End-User Computing",
}

ALLOWED_CERTS = {"CLF-C02", "DVA-C02"}

# Minimum body length below which a definition is almost certainly a stub /
# "duplicate skipped at merge time" leftover and not useful to learners.
MIN_DEFINITION_CHARS = 30


@pytest.fixture(scope="module")
def entries() -> list[dict]:
    raw = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), "Top-level JSON must be an object"
    assert "entries" in raw, "Missing top-level 'entries' key"
    assert isinstance(raw["entries"], list), "'entries' must be a list"
    return raw["entries"]


def test_glossary_has_meaningful_size(entries: list[dict]) -> None:
    assert len(entries) >= 200, f"Expected at least 200 glossary entries, found {len(entries)}"


def test_no_duplicate_terms(entries: list[dict]) -> None:
    seen: dict[str, int] = {}
    for e in entries:
        key = e["term"].lower().strip()
        seen[key] = seen.get(key, 0) + 1
    dupes = {k: v for k, v in seen.items() if v > 1}
    assert not dupes, f"Duplicate terms (case-insensitive): {dupes}"


def test_every_entry_has_required_fields(entries: list[dict]) -> None:
    for i, e in enumerate(entries):
        for field in ("term", "category", "certs", "definition"):
            assert field in e, f"Entry {i} ({e.get('term', '?')}) missing required field: {field}"


def test_categories_are_in_allowlist(entries: list[dict]) -> None:
    for e in entries:
        assert e["category"] in ALLOWED_CATEGORIES, (
            f"Entry {e['term']!r} has unknown category {e['category']!r}. "
            f"Add it to ALLOWED_CATEGORIES in tests/test_glossary.py or fix the JSON."
        )


def test_certs_are_in_allowlist(entries: list[dict]) -> None:
    for e in entries:
        assert isinstance(e["certs"], list), f"Entry {e['term']!r}: certs must be a list"
        assert e["certs"], f"Entry {e['term']!r}: certs must be non-empty"
        for c in e["certs"]:
            assert c in ALLOWED_CERTS, f"Entry {e['term']!r}: unknown cert {c!r}"


def test_definitions_are_substantive(entries: list[dict]) -> None:
    """Catch stub definitions like 'Already documented; duplicate skipped at merge time.'"""
    stubs = [
        e for e in entries
        if len(e.get("definition", "").strip()) < MIN_DEFINITION_CHARS
        or "duplicate skipped" in e.get("definition", "").lower()
    ]
    assert not stubs, (
        f"Stub / placeholder definitions found: "
        f"{[(e['term'], e['definition'][:60]) for e in stubs]}"
    )


def test_aliases_are_lists(entries: list[dict]) -> None:
    for e in entries:
        aliases = e.get("aliases", [])
        assert isinstance(aliases, list), f"Entry {e['term']!r}: aliases must be a list"
        for a in aliases:
            assert isinstance(a, str), f"Entry {e['term']!r}: alias {a!r} must be a string"


def test_term_is_non_empty_string(entries: list[dict]) -> None:
    for e in entries:
        term = e.get("term")
        assert isinstance(term, str) and term.strip(), f"Empty / non-string term: {e!r}"


def test_definition_text_has_no_html_braces(entries: list[dict]) -> None:
    """Catch broken JSON-escaping that left literal '{' / '}' in the definition.

    Markdown / inline references are fine; we just block raw template braces
    that would suggest a templating bug.
    """
    pattern = re.compile(r"\{\{|\}\}")
    bad = [e["term"] for e in entries if pattern.search(e.get("definition", ""))]
    assert not bad, f"Entries with raw template braces: {bad}"
