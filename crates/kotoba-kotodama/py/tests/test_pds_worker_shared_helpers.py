"""Pure helper tests for pds_* worker primitives.

All pds_* modules share the same helper surface:
  _utc_now_iso()
  _sign_body(secret, body)
  PDS_DID constant

Parametrized across all 6 modules:
  pds_heartbeat / pds_discover_cache / pds_domain_coverage /
  pds_key_rotation / pds_mitama_cron / pds_outbox
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

_PDS_MODULE_NAMES = [
    "pds_heartbeat",
    "pds_discover_cache",
    "pds_domain_coverage",
    "pds_key_rotation",
    "pds_mitama_cron",
    "pds_outbox",
]


def _load(name: str) -> Any:
    return importlib.import_module(f"kotodama.primitives.{name}")


# ─── _utc_now_iso ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_utc_now_iso_returns_string(mod_name: str):
    mod = _load(mod_name)
    assert isinstance(mod._utc_now_iso(), str)


@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_utc_now_iso_ends_with_z(mod_name: str):
    mod = _load(mod_name)
    assert mod._utc_now_iso().endswith("Z")


@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_utc_now_iso_contains_t(mod_name: str):
    mod = _load(mod_name)
    assert "T" in mod._utc_now_iso()


@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_utc_now_iso_has_date_part(mod_name: str):
    mod = _load(mod_name)
    ts = mod._utc_now_iso()
    # At minimum 20 chars: 2026-01-01T00:00:00Z
    assert len(ts) >= 20


# ─── _sign_body ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_sign_body_returns_string(mod_name: str):
    mod = _load(mod_name)
    result = mod._sign_body("mysecret", b"hello")
    assert isinstance(result, str)


@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_sign_body_is_hex(mod_name: str):
    mod = _load(mod_name)
    result = mod._sign_body("secret", b"body")
    int(result, 16)  # raises ValueError if not hex


@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_sign_body_is_deterministic(mod_name: str):
    mod = _load(mod_name)
    a = mod._sign_body("secret", b"body")
    b = mod._sign_body("secret", b"body")
    assert a == b


@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_sign_body_differs_by_secret(mod_name: str):
    mod = _load(mod_name)
    a = mod._sign_body("secret1", b"body")
    b = mod._sign_body("secret2", b"body")
    assert a != b


@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_sign_body_differs_by_body(mod_name: str):
    mod = _load(mod_name)
    a = mod._sign_body("secret", b"body1")
    b = mod._sign_body("secret", b"body2")
    assert a != b


@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_sign_body_64_hex_chars(mod_name: str):
    mod = _load(mod_name)
    result = mod._sign_body("s", b"x")
    assert len(result) == 64  # SHA-256 hex


# ─── PDS_DID constant ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_did_starts_with_did(mod_name: str):
    mod = _load(mod_name)
    assert mod.PDS_DID.startswith("did:")


@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_did_contains_atproto_etzhayyim_ai(mod_name: str):
    mod = _load(mod_name)
    assert "atproto.etzhayyim.com" in mod.PDS_DID


@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_did_is_string(mod_name: str):
    mod = _load(mod_name)
    assert isinstance(mod.PDS_DID, str)


# ─── Collection constant (module-specific name) ───────────────────────────────

@pytest.mark.parametrize("mod_name", _PDS_MODULE_NAMES)
def test_pds_collection_constant_starts_with_ai_etzhayyim(mod_name: str):
    mod = _load(mod_name)
    # Each module has exactly one COLLECTION constant ending in _COLLECTION
    collection_attrs = [
        attr for attr in dir(mod)
        if attr.endswith("_COLLECTION") and isinstance(getattr(mod, attr), str)
    ]
    assert len(collection_attrs) >= 1
    for attr in collection_attrs:
        val = getattr(mod, attr)
        assert val.startswith("com.etzhayyim.apps.pds."), f"{mod_name}.{attr} = {val!r}"
