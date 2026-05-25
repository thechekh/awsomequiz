"""Migrate the legacy SQLite quiz dump into Supabase Postgres.

Source schema (SQLite):
    tests(id, test_name, test_code, ...)
    test_questions(id, test_id, question_number, image_path, ...)
    questions(id, test_question_id, question_text, ...)
    answer_options(id, question_id, option_letter, option_text, is_correct, description, ...)

Target schema (Postgres): see supabase/migrations/0001_schema.sql.

Mapping:
    test_questions.question_number     -> questions.external_id (text)
    questions.question_text            -> questions.stem
    (>1 correct options)               -> questions.type = 'multiple', else 'single'
    answer_options.option_letter       -> options.label
    answer_options.option_text         -> options.text
    answer_options.is_correct          -> options.is_correct
    answer_options.description         -> options.explanation_detailed

Idempotency: upserts on natural keys (certification_id+external_id; question_id+label).
Safe to re-run; later runs refresh stem/text/explanation if the SQLite was updated.

Auth: connects to Postgres directly via SUPABASE_DB_URL (NOT via the REST API),
so it uses the service role / superuser connection and bypasses RLS.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from collections.abc import Iterable
from pathlib import Path

# psycopg is imported lazily inside main() so --dry-run works without installing deps.

# Local Supabase CLI default postgres URL.
DEFAULT_LOCAL_DB_URL = "postgresql://postgres:postgres@localhost:54322/postgres"
BATCH_SIZE = 500


def load_sqlite(sqlite_path: Path) -> list[dict]:
    """Read the SQLite dump and return a list of normalized question dicts.

    Returns one dict per question, each shaped like:
        {
            "external_id": "1",
            "stem": "...",
            "type": "single" | "multiple",
            "options": [
                {"label": "A", "text": "...", "is_correct": False, "description": "..."},
                ...
            ],
        }
    """
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite dump not found at {sqlite_path}")

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                tq.question_number AS question_number,
                q.question_text    AS question_text,
                ao.option_letter   AS option_letter,
                ao.option_text     AS option_text,
                ao.is_correct      AS is_correct,
                ao.description     AS description
            FROM test_questions tq
            JOIN questions q       ON q.test_question_id = tq.id
            JOIN answer_options ao ON ao.question_id = q.id
            ORDER BY tq.question_number, ao.option_letter
            """
        ).fetchall()
    finally:
        conn.close()

    by_qn: dict[int, dict] = {}
    for r in rows:
        qn = r["question_number"]
        if qn not in by_qn:
            by_qn[qn] = {
                "external_id": str(qn),
                "stem": r["question_text"],
                "options": [],
            }
        by_qn[qn]["options"].append(
            {
                "label": r["option_letter"],
                "text": r["option_text"],
                "is_correct": bool(r["is_correct"]),
                "description": r["description"],
            }
        )

    questions: list[dict] = []
    for qn in sorted(by_qn.keys()):
        q = by_qn[qn]
        correct_count = sum(1 for o in q["options"] if o["is_correct"])
        # Defensive: a question with 0 correct options would still be migrated as
        # "single" but flagged via stderr so we can spot data issues.
        if correct_count == 0:
            print(f"WARN: question {q['external_id']} has 0 correct options", file=sys.stderr)
        q["type"] = "multiple" if correct_count > 1 else "single"
        q["options"].sort(key=lambda o: o["label"])
        questions.append(q)
    return questions


def chunked(seq: list, size: int) -> Iterable[list]:
    """Yield successive `size`-sized chunks from `seq`."""
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def get_certification_id(cur, code: str) -> str:
    """Resolve a certification UUID by its short code (e.g. 'CLF-C02')."""
    cur.execute("SELECT id FROM public.certifications WHERE code = %s", (code,))
    row = cur.fetchone()
    if row is None:
        raise SystemExit(
            f"Certification with code '{code}' not found. "
            f"Did you run `supabase db reset` (which applies supabase/seed.sql)?"
        )
    return row["id"]


def upsert_questions(
    cur,
    certification_id: str,
    source: str,
    questions: list[dict],
) -> dict[str, str]:
    """Upsert questions in batches, returning a map of external_id -> question UUID."""
    id_map: dict[str, str] = {}
    sql = """
        INSERT INTO public.questions (certification_id, external_id, stem, type, source)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (certification_id, external_id) DO UPDATE SET
            stem       = EXCLUDED.stem,
            type       = EXCLUDED.type,
            source     = EXCLUDED.source,
            updated_at = now()
        RETURNING id, external_id
    """
    for batch in chunked(questions, BATCH_SIZE):
        for q in batch:
            cur.execute(sql, (certification_id, q["external_id"], q["stem"], q["type"], source))
            row = cur.fetchone()
            id_map[row["external_id"]] = row["id"]
    return id_map


def upsert_options(
    cur,
    question_id_map: dict[str, str],
    questions: list[dict],
) -> int:
    """Upsert options in batches. Returns total option count."""
    sql = """
        INSERT INTO public.options (question_id, label, text, is_correct, explanation_detailed)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (question_id, label) DO UPDATE SET
            text                  = EXCLUDED.text,
            is_correct            = EXCLUDED.is_correct,
            explanation_detailed  = EXCLUDED.explanation_detailed
    """
    rows: list[tuple] = []
    for q in questions:
        qid = question_id_map[q["external_id"]]
        for opt in q["options"]:
            rows.append((qid, opt["label"], opt["text"], opt["is_correct"], opt["description"]))

    total = 0
    for batch in chunked(rows, BATCH_SIZE):
        cur.executemany(sql, batch)
        total += len(batch)
    return total


def verify_counts(
    cur,
    certification_id: str,
    expected_questions: int,
    expected_options: int,
) -> tuple[int, int]:
    """Read back row counts and compare against what we just inserted."""
    cur.execute(
        "SELECT COUNT(*) AS n FROM public.questions WHERE certification_id = %s",
        (certification_id,),
    )
    q_count = cur.fetchone()["n"]
    cur.execute(
        """
        SELECT COUNT(*) AS n FROM public.options o
        JOIN public.questions q ON q.id = o.question_id
        WHERE q.certification_id = %s
        """,
        (certification_id,),
    )
    o_count = cur.fetchone()["n"]

    print(f"  Verified: {q_count} questions, {o_count} options in Postgres")
    if q_count != expected_questions:
        print(
            f"WARN: question count mismatch (expected {expected_questions}, got {q_count})",
            file=sys.stderr,
        )
    if o_count != expected_options:
        print(
            f"WARN: option count mismatch (expected {expected_options}, got {o_count})",
            file=sys.stderr,
        )
    return q_count, o_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sqlite", type=Path, required=True, help="Path to the SQLite dump (e.g. dumps/CLF-C02.db)")
    parser.add_argument("--certification-code", required=True, help="Certification code seeded in Postgres (e.g. CLF-C02)")
    parser.add_argument(
        "--db-url",
        default=os.environ.get("SUPABASE_DB_URL", DEFAULT_LOCAL_DB_URL),
        help="Postgres connection string (defaults to $SUPABASE_DB_URL or local Supabase CLI)",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Value written to questions.source (defaults to 'sqlite:<filename>')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse SQLite, print summary, do not write to Postgres",
    )
    args = parser.parse_args()

    print(f"Reading SQLite dump: {args.sqlite}")
    questions = load_sqlite(args.sqlite)
    total_q = len(questions)
    total_o = sum(len(q["options"]) for q in questions)
    multi_q = sum(1 for q in questions if q["type"] == "multiple")
    print(f"  Parsed: {total_q} questions ({multi_q} multi-answer), {total_o} options")

    if args.dry_run:
        print("\nDRY RUN -- no writes performed. Sample question:")
        sample = questions[0]
        print(f"  external_id={sample['external_id']}  type={sample['type']}")
        print(f"  stem={sample['stem'][:100]}...")
        for o in sample["options"]:
            mark = "*" if o["is_correct"] else " "
            print(f"    [{mark}] {o['label']}. {o['text'][:80]}...")
        return 0

    source = args.source or f"sqlite:{args.sqlite.name}"
    print(f"\nConnecting to Postgres: {_redact(args.db_url)}")

    import psycopg  # lazy: dry-run path above doesn't need it
    from psycopg.rows import dict_row

    with psycopg.connect(args.db_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cert_id = get_certification_id(cur, args.certification_code)
            print(f"  Certification '{args.certification_code}' -> {cert_id}")

            print(f"\nUpserting {total_q} questions in batches of {BATCH_SIZE}...")
            id_map = upsert_questions(cur, cert_id, source, questions)

            print(f"Upserting {total_o} options in batches of {BATCH_SIZE}...")
            inserted_opts = upsert_options(cur, id_map, questions)
            print(f"  Wrote {inserted_opts} option rows")

        # Commit before verification so the SELECT sees our writes.
        conn.commit()

        with conn.cursor() as cur:
            print("\nVerifying counts...")
            verify_counts(cur, cert_id, total_q, total_o)

    print("\nDone.")
    return 0


def _redact(db_url: str) -> str:
    """Strip the password from a postgres:// URL for safe logging."""
    if "@" not in db_url:
        return db_url
    head, tail = db_url.split("@", 1)
    if ":" in head:
        scheme_user, _password = head.rsplit(":", 1)
        return f"{scheme_user}:***@{tail}"
    return db_url


if __name__ == "__main__":
    raise SystemExit(main())
