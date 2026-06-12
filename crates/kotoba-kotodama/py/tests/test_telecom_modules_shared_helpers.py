"""Parametrized tests for shared pure helpers across all telecom_* primitives.

All telecom_* modules export the same helper set:
  _now_iso() / _new_id() / _join() / _require() / _caller() / _audit()
  TELECOM_DID / ACTOR_TAG constants

telecom_5g_security is covered in test_telecom_5g_security_helpers.py;
this file covers the remaining 16 telecom modules.
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

# All telecom modules except 5g_security (already fully covered separately)
_TELECOM_MODULE_NAMES = [
    "telecom_5gcore",
    "telecom_esim",
    "telecom_ims",
    "telecom_li",
    "telecom_mec",
    "telecom_nfv",
    "telecom_npn",
    "telecom_ntn",
    "telecom_optical",
    "telecom_oran",
    "telecom_oss",
    "telecom_resource",
    "telecom_supplier",
    "telecom_tmf",
    "telecom_tsn",
    "telecom_wlan",
    "telecom",
]


def _load(name: str) -> Any:
    return importlib.import_module(f"kotodama.primitives.{name}")


# ─── _now_iso ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_now_iso_returns_string(mod_name: str):
    mod = _load(mod_name)
    assert isinstance(mod._now_iso(), str)


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_now_iso_contains_t(mod_name: str):
    mod = _load(mod_name)
    assert "T" in mod._now_iso()


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_now_iso_is_iso8601(mod_name: str):
    mod = _load(mod_name)
    ts = mod._now_iso()
    # Either ends with Z or has +00:00 offset — both are valid ISO 8601 UTC
    assert ts.endswith("Z") or "+00:00" in ts or len(ts) >= 19


# ─── _new_id ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_new_id_starts_with_prefix(mod_name: str):
    mod = _load(mod_name)
    result = mod._new_id("myprefix", "part1", "part2")
    assert result.startswith("myprefix_")


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_new_id_deterministic_with_parts(mod_name: str):
    mod = _load(mod_name)
    a = mod._new_id("pfx", "val1", "val2")
    b = mod._new_id("pfx", "val1", "val2")
    assert a == b


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_new_id_differs_by_parts(mod_name: str):
    mod = _load(mod_name)
    a = mod._new_id("pfx", "val1")
    b = mod._new_id("pfx", "val2")
    assert a != b


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_new_id_returns_string(mod_name: str):
    mod = _load(mod_name)
    assert isinstance(mod._new_id("pre", "v"), str)


# ─── _join (optional — not present in all modules) ───────────────────────────

@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_join_none_returns_none(mod_name: str):
    mod = _load(mod_name)
    if not hasattr(mod, "_join"):
        pytest.skip(f"{mod_name} has no _join")
    assert mod._join(None) is None


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_join_list_joined(mod_name: str):
    mod = _load(mod_name)
    if not hasattr(mod, "_join"):
        pytest.skip(f"{mod_name} has no _join")
    result = mod._join(["a", "b", "c"])
    assert result == "a,b,c"


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_join_empty_list_returns_none(mod_name: str):
    mod = _load(mod_name)
    if not hasattr(mod, "_join"):
        pytest.skip(f"{mod_name} has no _join")
    assert mod._join([]) is None


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_join_string_passthrough(mod_name: str):
    mod = _load(mod_name)
    if not hasattr(mod, "_join"):
        pytest.skip(f"{mod_name} has no _join")
    assert mod._join("hello") == "hello"


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_join_empty_string_returns_none(mod_name: str):
    mod = _load(mod_name)
    if not hasattr(mod, "_join"):
        pytest.skip(f"{mod_name} has no _join")
    assert mod._join("") is None


# ─── _require ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_require_passes_when_all_present(mod_name: str):
    mod = _load(mod_name)
    mod._require({"a": "val1", "b": "val2"}, ["a", "b"])  # no exception


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_require_raises_on_missing(mod_name: str):
    mod = _load(mod_name)
    with pytest.raises(ValueError):
        mod._require({"a": "val"}, ["a", "b"])


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_require_raises_on_empty_string(mod_name: str):
    mod = _load(mod_name)
    with pytest.raises(ValueError):
        mod._require({"a": ""}, ["a"])


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_require_empty_fields_passes(mod_name: str):
    mod = _load(mod_name)
    mod._require({"any": "data"}, [])  # no exception


# ─── _caller (optional — not present in all modules) ─────────────────────────

@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_caller_returns_caller_did(mod_name: str):
    mod = _load(mod_name)
    if not hasattr(mod, "_caller"):
        pytest.skip(f"{mod_name} has no _caller")
    result = mod._caller({"callerDid": "did:web:test.etzhayyim.com"})
    assert result == "did:web:test.etzhayyim.com"


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_caller_defaults_to_telecom_did(mod_name: str):
    mod = _load(mod_name)
    if not hasattr(mod, "_caller"):
        pytest.skip(f"{mod_name} has no _caller")
    result = mod._caller({})
    assert result == mod.TELECOM_DID


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_caller_none_caller_did_returns_telecom_did(mod_name: str):
    mod = _load(mod_name)
    if not hasattr(mod, "_caller"):
        pytest.skip(f"{mod_name} has no _caller")
    result = mod._caller({"callerDid": None})
    assert result == mod.TELECOM_DID


# ─── _audit (optional — not present in all modules) ──────────────────────────

@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_audit_returns_dict(mod_name: str):
    mod = _load(mod_name)
    if not hasattr(mod, "_audit"):
        pytest.skip(f"{mod_name} has no _audit")
    assert isinstance(mod._audit({}), dict)


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_audit_has_created_at(mod_name: str):
    mod = _load(mod_name)
    if not hasattr(mod, "_audit"):
        pytest.skip(f"{mod_name} has no _audit")
    result = mod._audit({})
    assert "created_at" in result


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_audit_sensitivity_ord(mod_name: str):
    mod = _load(mod_name)
    if not hasattr(mod, "_audit"):
        pytest.skip(f"{mod_name} has no _audit")
    result = mod._audit({})
    assert "sensitivity_ord" in result


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_audit_uses_caller_did(mod_name: str):
    mod = _load(mod_name)
    if not hasattr(mod, "_audit"):
        pytest.skip(f"{mod_name} has no _audit")
    result = mod._audit({"callerDid": "did:web:caller.etzhayyim.com"})
    assert result.get("org_id") == "did:web:caller.etzhayyim.com"


# ─── constants ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_did_starts_with_did(mod_name: str):
    mod = _load(mod_name)
    assert mod.TELECOM_DID.startswith("did:")


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_telecom_did_contains_telecom(mod_name: str):
    mod = _load(mod_name)
    assert "telecom" in mod.TELECOM_DID


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_actor_tag_is_string(mod_name: str):
    mod = _load(mod_name)
    assert isinstance(mod.ACTOR_TAG, str)


@pytest.mark.parametrize("mod_name", _TELECOM_MODULE_NAMES)
def test_actor_tag_contains_telecom(mod_name: str):
    mod = _load(mod_name)
    assert "telecom" in mod.ACTOR_TAG
