"""Load Anki-style flashcards from CSVs in `questions/` into Supabase.

CSV mapping:
    basic.csv          (Front, Back)                  -> "AWS Basics" deck
    aws_framework.csv  (aspect, description, framework) -> split by `framework`:
                                                       WAF / CAF / Migration Strategies
    aws_service.csv    (service, description)         -> "AWS Services" deck

Idempotent: deck rows upsert on `code`; cards upsert on (deck_id, external_id)
where external_id = sha256(front)[:32]. Re-running just refreshes back/category.

Auth: connects via SUPABASE_DB_URL (service-role-equivalent direct Postgres),
bypassing RLS. Same convention as migrate_sqlite_to_supabase.py.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys
from pathlib import Path

DEFAULT_LOCAL_DB_URL = "postgresql://postgres:postgres@localhost:54322/postgres"


# Maps a `framework` column value to (deck_code, deck_name, deck_description, display_order).
FRAMEWORK_DECKS = {
    "WAF": ("waf", "AWS Well-Architected Framework", "The 6 pillars of WAF", 2),
    "CAF": ("caf", "AWS Cloud Adoption Framework", "The 6 perspectives of CAF", 3),
    "Migration Strategies": (
        "migration_6rs",
        "AWS Migration Strategies (6 Rs)",
        "Rehost / Replatform / Refactor / Retire / Retain / Repurchase",
        4,
    ),
}


def _hash_front(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:32]


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _certification_id(cur, code: str) -> str:
    cur.execute("SELECT id FROM public.certifications WHERE code = %s", (code,))
    row = cur.fetchone()
    if row is None:
        raise SystemExit(
            f"Certification with code '{code}' not found. "
            f"Run `supabase db reset` (which applies supabase/seed.sql)."
        )
    return row["id"]


def _upsert_deck(
    cur,
    cert_id: str,
    code: str,
    name: str,
    description: str | None,
    display_order: int,
) -> str:
    cur.execute(
        """
        INSERT INTO public.flashcard_decks (certification_id, code, name, description, display_order)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (code) DO UPDATE SET
            certification_id = EXCLUDED.certification_id,
            name             = EXCLUDED.name,
            description      = EXCLUDED.description,
            display_order    = EXCLUDED.display_order
        RETURNING id
        """,
        (cert_id, code, name, description, display_order),
    )
    return cur.fetchone()["id"]


def _upsert_cards(cur, deck_id: str, cards: list[dict]) -> int:
    if not cards:
        return 0
    sql = """
        INSERT INTO public.flashcards (deck_id, external_id, front, back, category)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (deck_id, external_id) DO UPDATE SET
            front      = EXCLUDED.front,
            back       = EXCLUDED.back,
            category   = EXCLUDED.category,
            is_active  = true,
            updated_at = now()
    """
    rows = [
        (deck_id, _hash_front(c["front"]), c["front"], c["back"], c.get("category"))
        for c in cards
    ]
    cur.executemany(sql, rows)
    return len(rows)


def load(db_url: str, cert_code: str, questions_dir: Path) -> None:
    import psycopg  # lazy: dry-listing the CSVs doesn't need it
    from psycopg.rows import dict_row

    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cert_id = _certification_id(cur, cert_code)
            print(f"Certification '{cert_code}' -> {cert_id}")

            # --- basic.csv -> "AWS Basics" deck -----------------------------
            basic_rows = _read_csv(questions_dir / "basic.csv")
            basic_cards = [{"front": r["Front"], "back": r["Back"]} for r in basic_rows]
            deck_id = _upsert_deck(
                cur, cert_id, "basics", "AWS Basics", "Foundational AWS facts", 1
            )
            n = _upsert_cards(cur, deck_id, basic_cards)
            print(f"  AWS Basics: {n} cards")

            # --- aws_framework.csv -> WAF / CAF / Migration decks -----------
            framework_rows = _read_csv(questions_dir / "aws_framework.csv")
            by_fw: dict[str, list[dict]] = {}
            for r in framework_rows:
                by_fw.setdefault(r["framework"], []).append(r)
            for fw_key, rows in by_fw.items():
                meta = FRAMEWORK_DECKS.get(fw_key)
                if not meta:
                    print(f"  WARN: skipping unknown framework '{fw_key}'", file=sys.stderr)
                    continue
                code, name, desc, order = meta
                deck_id = _upsert_deck(cur, cert_id, code, name, desc, order)
                cards = [
                    {
                        "front": r["aspect"],
                        "back": r["description"],
                        "category": r["framework"],
                    }
                    for r in rows
                ]
                n = _upsert_cards(cur, deck_id, cards)
                print(f"  {name}: {n} cards")

            # --- aws_service.csv -> "AWS Services" deck ---------------------
            service_rows = _read_csv(questions_dir / "aws_service.csv")
            service_cards = [
                {"front": r["service"], "back": r["description"]} for r in service_rows
            ]
            deck_id = _upsert_deck(
                cur,
                cert_id,
                "aws_services",
                "AWS Services",
                "What each AWS service does",
                5,
            )
            n = _upsert_cards(cur, deck_id, service_cards)
            print(f"  AWS Services: {n} cards")

        conn.commit()

        # Verify counts
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM public.flashcards f "
                "JOIN public.flashcard_decks d ON d.id = f.deck_id "
                "WHERE d.certification_id = %s",
                (cert_id,),
            )
            total = cur.fetchone()["n"]
            print(f"\nVerified: {total} flashcards in Postgres for {cert_code}.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--questions-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "questions",
        help="Directory containing basic.csv / aws_framework.csv / aws_service.csv",
    )
    parser.add_argument(
        "--certification-code",
        default="CLF-C02",
        help="Certification to attach the decks to (default CLF-C02)",
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get("SUPABASE_DB_URL", DEFAULT_LOCAL_DB_URL),
        help="Postgres connection string (defaults to $SUPABASE_DB_URL or local Supabase CLI)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Parse CSVs and print summary; no DB writes",
    )
    args = parser.parse_args()

    if args.list:
        print(f"Reading CSVs from: {args.questions_dir}")
        for name in ("basic.csv", "aws_framework.csv", "aws_service.csv"):
            rows = _read_csv(args.questions_dir / name)
            print(f"  {name}: {len(rows)} rows")
        return 0

    print(f"Loading flashcards into: {_redact(args.db_url)}")
    load(args.db_url, args.certification_code, args.questions_dir)
    print("\nDone.")
    return 0


def _redact(db_url: str) -> str:
    if "@" not in db_url:
        return db_url
    head, tail = db_url.split("@", 1)
    if ":" in head:
        scheme_user, _password = head.rsplit(":", 1)
        return f"{scheme_user}:***@{tail}"
    return db_url


if __name__ == "__main__":
    raise SystemExit(main())
