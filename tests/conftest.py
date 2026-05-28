"""Pytest fixture / sys.path setup shared across the test suite.

Two responsibilities:
 1. Add the project root to sys.path so `import app.queries` works regardless
    of where pytest is invoked from.
 2. Stub the supabase + supabase.client modules so test files can import
    `app.db` / `app.queries` / `app.session` even when supabase isn't
    installed (e.g. on a build host without C++ compilers for pyiceberg).
    Tests that need actual Supabase behaviour mock `get_supabase` directly.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _ensure_supabase_stub() -> None:
    """Inject a placeholder `supabase` module if the real one isn't available."""
    try:
        from supabase import Client, create_client  # noqa: F401
        return
    except ImportError:
        pass

    supabase_mod = types.ModuleType("supabase")
    supabase_mod.Client = MagicMock  # type: ignore[attr-defined]
    supabase_mod.create_client = MagicMock(return_value=MagicMock())  # type: ignore[attr-defined]
    sys.modules["supabase"] = supabase_mod

    client_submod = types.ModuleType("supabase.client")
    client_submod.ClientOptions = MagicMock  # type: ignore[attr-defined]
    sys.modules["supabase.client"] = client_submod


_ensure_supabase_stub()
