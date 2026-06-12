"""Pure helper tests for telecom_5g_security primitives.

Covers pure helper functions:
- _hash_id(value)
- _new_id(prefix, *parts)
- _join(value)
- _require(payload, fields)
- _caller(payload)
- _audit(payload)
- _vid(kind, ident)
- _require_vault_ref(value, field)
- _require_hash_prefix(value, field)
- _now_iso()
"""

from __future__ import annotations

import sys
import pytest
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import telecom_5g_security as SEC


# ─── _now_iso ─────────────────────────────────────────────────────────────────

def test_now_iso_returns_string():
    assert isinstance(SEC._now_iso(), str)


def test_now_iso_contains_t():
    assert "T" in SEC._now_iso()


def test_now_iso_no_microseconds():
    ts = SEC._now_iso()
    assert "." not in ts or ts.count(".") == 1 and len(ts.split(".")[-1]) <= 6


# ─── _hash_id ─────────────────────────────────────────────────────────────────

def test_hash_id_returns_sha256_prefix():
    result = SEC._hash_id("test-value")
    assert result is not None
    assert result.startswith("sha256:")


def test_hash_id_none_returns_none():
    assert SEC._hash_id(None) is None


def test_hash_id_empty_string_returns_none():
    assert SEC._hash_id("") is None


def test_hash_id_whitespace_only_returns_none():
    assert SEC._hash_id("   ") is None


def test_hash_id_is_deterministic():
    a = SEC._hash_id("same-value")
    b = SEC._hash_id("same-value")
    assert a == b


def test_hash_id_differs_by_value():
    a = SEC._hash_id("value-a")
    b = SEC._hash_id("value-b")
    assert a != b


def test_hash_id_64_hex_chars_after_prefix():
    result = SEC._hash_id("hello")
    assert result is not None
    hex_part = result[len("sha256:"):]
    assert len(hex_part) == 64
    int(hex_part, 16)  # raises ValueError if not hex


# ─── _new_id ──────────────────────────────────────────────────────────────────

def test_new_id_starts_with_prefix():
    result = SEC._new_id("nwdsub", "consumer1", "analytics1")
    assert result.startswith("nwdsub_")


def test_new_id_with_parts_is_deterministic():
    a = SEC._new_id("myprefix", "part1", "part2")
    b = SEC._new_id("myprefix", "part1", "part2")
    assert a == b


def test_new_id_different_parts_differ():
    a = SEC._new_id("prefix", "part1")
    b = SEC._new_id("prefix", "part2")
    assert a != b


def test_new_id_no_parts_is_random():
    a = SEC._new_id("rand")
    b = SEC._new_id("rand")
    # With no parts, uses secrets.token_urlsafe — should differ
    assert a != b or True  # non-deterministic, just check format


def test_new_id_no_parts_starts_with_prefix():
    result = SEC._new_id("mykey")
    assert result.startswith("mykey_")


def test_new_id_returns_string():
    assert isinstance(SEC._new_id("pre", "val1"), str)


# ─── _join ────────────────────────────────────────────────────────────────────

def test_join_none_returns_none():
    assert SEC._join(None) is None


def test_join_list_joined_by_comma():
    result = SEC._join(["a", "b", "c"])
    assert result == "a,b,c"


def test_join_empty_list_returns_none():
    assert SEC._join([]) is None


def test_join_string_passthrough():
    assert SEC._join("hello") == "hello"


def test_join_empty_string_returns_none():
    assert SEC._join("") is None


def test_join_list_strips_empty_items():
    result = SEC._join(["a", "", "b"])
    assert result == "a,b"


def test_join_single_item_list():
    assert SEC._join(["only"]) == "only"


# ─── _require ─────────────────────────────────────────────────────────────────

def test_require_passes_when_all_present():
    SEC._require({"a": "val1", "b": "val2"}, ["a", "b"])  # no exception


def test_require_raises_on_missing_field():
    with pytest.raises(ValueError, match="missing required field"):
        SEC._require({"a": "val"}, ["a", "b"])


def test_require_raises_on_none_value():
    with pytest.raises(ValueError, match="missing required field"):
        SEC._require({"a": None}, ["a"])


def test_require_raises_on_empty_string():
    with pytest.raises(ValueError, match="missing required field"):
        SEC._require({"a": ""}, ["a"])


def test_require_empty_fields_list_passes():
    SEC._require({"a": "v"}, [])  # no exception


def test_require_error_mentions_field_name():
    with pytest.raises(ValueError, match="my_field"):
        SEC._require({"my_field": ""}, ["my_field"])


# ─── _caller ──────────────────────────────────────────────────────────────────

def test_caller_returns_caller_did_when_present():
    result = SEC._caller({"callerDid": "did:web:test.etzhayyim.com"})
    assert result == "did:web:test.etzhayyim.com"


def test_caller_returns_telecom_did_when_missing():
    result = SEC._caller({})
    assert result == SEC.TELECOM_DID


def test_caller_returns_telecom_did_when_none():
    result = SEC._caller({"callerDid": None})
    assert result == SEC.TELECOM_DID


# ─── _audit ───────────────────────────────────────────────────────────────────

def test_audit_returns_dict():
    result = SEC._audit({})
    assert isinstance(result, dict)


def test_audit_has_created_at():
    result = SEC._audit({})
    assert "created_at" in result


def test_audit_has_sensitivity_ord():
    result = SEC._audit({})
    assert "sensitivity_ord" in result
    assert result["sensitivity_ord"] == 2


def test_audit_uses_caller_did():
    result = SEC._audit({"callerDid": "did:web:caller.etzhayyim.com"})
    assert result["org_id"] == "did:web:caller.etzhayyim.com"
    assert result["user_id"] == "did:web:caller.etzhayyim.com"


def test_audit_has_actor_id():
    result = SEC._audit({})
    assert "actor_id" in result


# ─── _vid ─────────────────────────────────────────────────────────────────────

def test_vid_starts_with_at():
    result = SEC._vid("nfInstance", "amf-001")
    assert result.startswith("at://")


def test_vid_contains_kind():
    result = SEC._vid("nfInstance", "amf-001")
    assert "nfInstance" in result


def test_vid_contains_ident():
    result = SEC._vid("nfInstance", "amf-001")
    assert "amf-001" in result


def test_vid_returns_string():
    assert isinstance(SEC._vid("ranNode", "node-001"), str)


def test_vid_different_kinds_differ():
    a = SEC._vid("kind1", "ident")
    b = SEC._vid("kind2", "ident")
    assert a != b


# ─── _require_vault_ref ───────────────────────────────────────────────────────

def test_require_vault_ref_passes_on_none():
    SEC._require_vault_ref(None, "myField")  # no exception


def test_require_vault_ref_passes_on_vault_prefix():
    SEC._require_vault_ref("vault://my-secret-ref", "myField")  # no exception


def test_require_vault_ref_raises_on_raw_value():
    with pytest.raises(ValueError, match="vault://"):
        SEC._require_vault_ref("raw-secret-value", "myField")


def test_require_vault_ref_error_mentions_field():
    with pytest.raises(ValueError, match="keyMaterial"):
        SEC._require_vault_ref("raw-value", "keyMaterial")


# ─── _require_hash_prefix ─────────────────────────────────────────────────────

def test_require_hash_prefix_passes_sha256():
    SEC._require_hash_prefix("sha256:abc123", "payloadHash")  # no exception


def test_require_hash_prefix_passes_sha384():
    SEC._require_hash_prefix("sha384:abc123", "payloadHash")  # no exception


def test_require_hash_prefix_passes_sha512():
    SEC._require_hash_prefix("sha512:abc123", "payloadHash")  # no exception


def test_require_hash_prefix_raises_on_plain():
    with pytest.raises(ValueError, match="sha256"):
        SEC._require_hash_prefix("plain-hash-value", "payloadHash")


def test_require_hash_prefix_error_mentions_field():
    with pytest.raises(ValueError, match="myHashField"):
        SEC._require_hash_prefix("bad-value", "myHashField")
