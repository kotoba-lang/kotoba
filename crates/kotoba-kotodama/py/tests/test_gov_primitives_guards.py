"""Parametric early-return guard tests for all 140 gov_*.py country primitives.

Each gov_{iso3}.py exposes:
  task_gov_{iso3}_resolve_org_path(path="") → {"error": "missing path"}
  before any DB access — this is the only path tested here.

Tests that touch sync_cursor are excluded: in a full suite run some earlier
test file loads the real kotodama.db_sync (which needs RW_URL), making any
DB-reaching path unreliable.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from functools import lru_cache
from pathlib import Path

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# ── db_sync stub (best-effort: only takes effect if real module not yet loaded)
_db_stub = types.ModuleType("kotodama.db_sync")

def _noop_cursor():
    class _C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **kw): pass
        def fetchone(self): return None
        def fetchall(self): return []
        description = None
        rowcount = 0
    return _C()

_db_stub.sync_cursor = _noop_cursor  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama.db_sync", _db_stub)

# kotodama package stub (needed for spec_from_file_location loads)
if "kotodama" not in sys.modules:
    _pkg = types.ModuleType("kotodama")
    _pkg.__path__ = [str(_py_src / "kotodama")]  # type: ignore[attr-defined]
    _pkg.__package__ = "kotodama"
    sys.modules["kotodama"] = _pkg


# ── discover ISO3 codes ─────────────────────────────────────────────────────
_GOV_DIR = _py_src / "kotodama" / "primitives"
_ISO3_CODES = sorted(
    f.stem.split("_", 1)[1]
    for f in _GOV_DIR.glob("gov_*.py")
)


@lru_cache(maxsize=None)
def _load_gov(iso3: str):
    """Load gov_{iso3} with file-based loader.
    Ensures the stub is temporarily in sys.modules for the import.
    """
    key = f"_gov_guard_pure_{iso3}"
    if key in sys.modules:
        return sys.modules[key]
    # Temporarily inject stub so the import-time `from kotodama.db_sync import
    # sync_cursor` in gov_*.py picks up our noop version, even if the real module
    # is already loaded.
    real_db = sys.modules.get("kotodama.db_sync")
    sys.modules["kotodama.db_sync"] = _db_stub
    try:
        src = _GOV_DIR / f"gov_{iso3}.py"
        spec = importlib.util.spec_from_file_location(key, src)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules[key] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    finally:
        if real_db is not None:
            sys.modules["kotodama.db_sync"] = real_db
        elif "kotodama.db_sync" in sys.modules and sys.modules["kotodama.db_sync"] is _db_stub:
            pass  # stub is fine
    return mod


# ── parametric tests (path="" guard only — no DB access) ────────────────────

@pytest.mark.parametrize("iso3", _ISO3_CODES)
def test_resolve_org_path_empty_returns_error(iso3: str) -> None:
    mod = _load_gov(iso3)
    fn = getattr(mod, f"task_gov_{iso3}_resolve_org_path")
    result = asyncio.run(fn(path=""))
    assert "error" in result


@pytest.mark.parametrize("iso3", _ISO3_CODES)
def test_resolve_org_path_empty_error_mentions_path(iso3: str) -> None:
    mod = _load_gov(iso3)
    fn = getattr(mod, f"task_gov_{iso3}_resolve_org_path")
    result = asyncio.run(fn(path=""))
    assert "path" in result["error"]


@pytest.mark.parametrize("iso3", _ISO3_CODES)
def test_resolve_org_path_returns_dict(iso3: str) -> None:
    mod = _load_gov(iso3)
    fn = getattr(mod, f"task_gov_{iso3}_resolve_org_path")
    result = asyncio.run(fn(path=""))
    assert isinstance(result, dict)
