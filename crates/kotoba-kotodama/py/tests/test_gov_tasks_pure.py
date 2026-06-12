"""Pure-path tests for gov_* task functions (uses noop DB cursor).

Each gov_* module exposes 8 async task functions that read/write DB via
sync_cursor().  With an empty noop cursor all loops short-circuit, so
tasks return deterministic dicts without any real DB or HTTP.

Covers a representative sample of 10 modules across regions:
  afg, usa, fra, jpn, bra, deu, gbr, aus, can, chn
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# ── All 140 gov modules ──────────────────────────────────────────────────────
SAMPLE_CODES = [
    'afg', 'ago', 'alb', 'and', 'are', 'arg', 'atg', 'aus', 'aut', 'bel',
    'bgd', 'bgr', 'bhr', 'bih', 'blr', 'bol', 'bra', 'brb', 'brn', 'bwa',
    'can', 'che', 'chl', 'chn', 'civ', 'cmr', 'cod', 'col', 'cri', 'cub',
    'cyp', 'cze', 'deu', 'dma', 'dnk', 'dom', 'dza', 'ecu', 'egy', 'esp',
    'est', 'eth', 'fin', 'fji', 'fra', 'gbr', 'geo', 'gha', 'grc', 'grd',
    'gtm', 'guy', 'hkg', 'hnd', 'hrv', 'hti', 'hun', 'idn', 'ind', 'irl',
    'irn', 'irq', 'isl', 'ita', 'jam', 'jor', 'jpn', 'kaz', 'ken', 'kgz',
    'khm', 'kor', 'kwt', 'lao', 'lbn', 'lby', 'lka', 'ltu', 'lux', 'lva',
    'mar', 'mdg', 'mex', 'mhl', 'mkd', 'mlt', 'mmr', 'mne', 'mng', 'moz',
    'mys', 'nga', 'nic', 'nld', 'nor', 'npl', 'nzl', 'omn', 'pak', 'pan',
    'per', 'phl', 'png', 'pol', 'prk', 'prt', 'pry', 'pse', 'qat', 'rou',
    'rus', 'rwa', 'sau', 'sdn', 'sen', 'sgp', 'slv', 'srb', 'ssd', 'sur',
    'svk', 'svn', 'swe', 'tha', 'tjk', 'tkm', 'tls', 'tur', 'tza', 'uga',
    'ukr', 'ury', 'usa', 'uzb', 'ven', 'vnm', 'yem', 'zaf', 'zmb', 'zwe',
]


def _load_mod(code: str):
    name = f"kotodama.primitives.gov_{code}"
    if name not in sys.modules:
        importlib.import_module(name)
    return sys.modules[name]


def _make_sync_cursor_mock() -> MagicMock:
    """Return a callable mock that acts as a noop context-manager cursor."""
    cur = MagicMock()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    cur.description = []
    cm = MagicMock()
    cm.return_value.__enter__.return_value = cur
    cm.return_value.__exit__.return_value = False
    return cm


# ── seed_orgs ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_seed_orgs_returns_dict(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(getattr(mod, f"task_gov_{code}_seed_orgs")(limit=1))
        assert isinstance(result, dict)
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_seed_orgs_ok_true(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(getattr(mod, f"task_gov_{code}_seed_orgs")(limit=1))
        assert result.get("ok") is True
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_seed_orgs_has_seeded_key(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(getattr(mod, f"task_gov_{code}_seed_orgs")(limit=1))
        assert "seeded" in result
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


# ── resolve_org_path ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_resolve_org_path_empty_returns_error(code: str) -> None:
    mod = _load_mod(code)
    result = asyncio.run(getattr(mod, f"task_gov_{code}_resolve_org_path")(path=""))
    assert result.get("ok") is not True
    assert "error" in result


@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_resolve_org_path_missing_returns_error(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(
            getattr(mod, f"task_gov_{code}_resolve_org_path")(path="__nonexistent__")
        )
        assert "error" in result
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


# ── list_orgs ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_list_orgs_returns_dict(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(getattr(mod, f"task_gov_{code}_list_orgs")())
        assert isinstance(result, dict)
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_list_orgs_has_orgs_key(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(getattr(mod, f"task_gov_{code}_list_orgs")())
        assert "orgs" in result
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


# ── register_dids ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_register_dids_returns_dict(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(getattr(mod, f"task_gov_{code}_register_dids")(limit=1))
        assert isinstance(result, dict)
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_register_dids_ok_true_empty(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(getattr(mod, f"task_gov_{code}_register_dids")(limit=1))
        assert result.get("ok") is True
        assert result.get("registered") == 0
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


# ── follow_site_deps ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_follow_site_deps_returns_dict(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(getattr(mod, f"task_gov_{code}_follow_site_deps")(limit=1))
        assert isinstance(result, dict)
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_follow_site_deps_ok_true_empty(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(getattr(mod, f"task_gov_{code}_follow_site_deps")(limit=1))
        assert result.get("ok") is True
        assert result.get("followed") == 0
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


# ── sync_wet_updates ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_sync_wet_updates_returns_dict(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(getattr(mod, f"task_gov_{code}_sync_wet_updates")(limit=1))
        assert isinstance(result, dict)
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_sync_wet_updates_ok_true_empty(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(getattr(mod, f"task_gov_{code}_sync_wet_updates")(limit=1))
        assert result.get("ok") is True
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


# ── shinka ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_shinka_returns_dict(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(getattr(mod, f"task_gov_{code}_shinka")(limit=1))
        assert isinstance(result, dict)
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_shinka_ok_true_empty(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(getattr(mod, f"task_gov_{code}_shinka")(limit=1))
        assert result.get("ok") is True
        assert result.get("touched") == 0
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


# ── heartbeat_tick ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_heartbeat_tick_returns_dict(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(
            getattr(mod, f"task_gov_{code}_heartbeat_tick")(
                seedLimit=1, registerLimit=1, followLimit=1, ingestLimit=1, shinkaLimit=1,
            )
        )
        assert isinstance(result, dict)
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_heartbeat_tick_ok_true(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(
            getattr(mod, f"task_gov_{code}_heartbeat_tick")(
                seedLimit=1, registerLimit=1, followLimit=1, ingestLimit=1, shinkaLimit=1,
            )
        )
        assert result.get("ok") is True
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]


@pytest.mark.parametrize("code", SAMPLE_CODES)
def test_heartbeat_tick_has_all_keys(code: str) -> None:
    mod = _load_mod(code)
    mock_sc = _make_sync_cursor_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(
            getattr(mod, f"task_gov_{code}_heartbeat_tick")(
                seedLimit=1, registerLimit=1, followLimit=1, ingestLimit=1, shinkaLimit=1,
            )
        )
        for key in ("seeded", "registered", "followed", "wetUpdated", "shinkaPosted"):
            assert key in result, f"missing key '{key}' in heartbeat_tick result"
    finally:
        from kotodama.db_sync import sync_cursor as _real
        mod.sync_cursor = _real  # type: ignore[attr-defined]
