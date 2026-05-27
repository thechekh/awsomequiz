"""Smoke test: every importable module loads without error.

Catches silly issues like circular imports, typos in import paths, syntax that
ruff-format missed. Doesn't require a running Supabase -- the modules don't
make any DB calls at import time.

Run with: uv run pytest tests/
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_app_modules_import() -> None:
    """All `app.*` modules import cleanly."""
    for name in (
        "app",
        "app.auth",
        "app.cookies",
        "app.db",
        "app.queries",
        "app.session",
        "app.components",
        "app.components.runner",
    ):
        importlib.import_module(name)


def test_scripts_import() -> None:
    """The migration script's importable parts load (its lazy psycopg import
    means we don't need it installed to verify the top-of-file structure)."""
    # Importing as a module would trigger argparse parsing at top of __main__;
    # the script guards that under `if __name__ == "__main__"` so this is safe.
    importlib.import_module("scripts.migrate_sqlite_to_supabase")


def test_pages_have_required_pattern() -> None:
    """Every page under pages/ should at least be a valid Python module.

    We don't import them because they call st.set_page_config / st.title at
    module level, which would fail outside a Streamlit runtime. Instead we just
    verify the file compiles.
    """
    import py_compile

    pages_dir = PROJECT_ROOT / "pages"
    for path in pages_dir.glob("*.py"):
        py_compile.compile(str(path), doraise=True)


def test_streamlit_entry_compiles() -> None:
    """streamlit_app.py must compile (not import -- same st-runtime caveat)."""
    import py_compile

    py_compile.compile(str(PROJECT_ROOT / "streamlit_app.py"), doraise=True)
