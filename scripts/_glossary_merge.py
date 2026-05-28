"""Merge incoming JSON glossary entries into data/glossary.json.

Reads a JSON list from stdin; appends each entry whose `term` doesn't
already exist (case-insensitive). Writes the merged file back.

Usage:
    python scripts/_glossary_merge.py < batch.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if __name__ == "__main__":
    new_entries = json.loads(sys.stdin.read())
    path = Path("data/glossary.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    existing = {e["term"].lower() for e in data["entries"]}
    added = 0
    for entry in new_entries:
        key = entry["term"].lower()
        if key in existing:
            print(f"SKIP (exists): {entry['term']}", file=sys.stderr)
            continue
        data["entries"].append(entry)
        existing.add(key)
        added += 1
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Added {added}/{len(new_entries)} new entries. Total: {len(data['entries'])}.")
