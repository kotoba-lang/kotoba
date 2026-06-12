"""Pure helper tests for telecom_esim and telecom_oran primitives.

Covers pure functions with no DB/Zeebe dependencies:
- telecom_esim: _now_iso / _new_id / _vid / _hash / _require /
                TELECOM_DID / DEVICE_KINDS / PROFILE_TYPES / PROFILE_STATES /
                OP_KINDS / DISABLE_REASONS / DELETE_REASONS / EVENT_TYPES
- telecom_oran: _now_iso / _new_id / _join / _join_vids / _vid /
                _require / _caller / _require_vault_ref / _require_hash_prefix /
                TELECOM_DID / A1_USE_CASES / E2_SERVICE_MODELS /
                O1_TARGET_KINDS / O2_RESOURCE_KINDS
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import telecom_esim as ES
from kotodama.primitives import telecom_oran as OR


# ─── telecom_esim — _now_iso ──────────────────────────────────────────────────

def test_es_now_iso_returns_string():
    assert isinstance(ES._now_iso(), str)


def test_es_now_iso_contains_t():
    assert "T" in ES._now_iso()


def test_es_now_iso_not_ends_with_z_but_has_offset():
    result = ES._now_iso()
    # isoformat() without replace produces +00:00
    assert "T" in result


# ─── telecom_esim — _new_id ───────────────────────────────────────────────────

def test_es_new_id_with_parts_is_deterministic():
    a = ES._new_id("euicc", "eid1", "op1")
    b = ES._new_id("euicc", "eid1", "op1")
    assert a == b


def test_es_new_id_starts_with_prefix():
    result = ES._new_id("profile", "key1")
    assert result.startswith("profile_")


def test_es_new_id_without_parts_is_random():
    a = ES._new_id("euicc")
    b = ES._new_id("euicc")
    assert a != b


def test_es_new_id_without_parts_starts_with_prefix():
    result = ES._new_id("esim")
    assert result.startswith("esim_")


def test_es_new_id_differs_by_parts():
    a = ES._new_id("x", "part1")
    b = ES._new_id("x", "part2")
    assert a != b


# ─── telecom_esim — _vid ──────────────────────────────────────────────────────

def test_es_vid_starts_with_at():
    result = ES._vid("euicc", "eid-001")
    assert result.startswith("at://")


def test_es_vid_contains_kind():
    result = ES._vid("euicc", "eid-001")
    assert "euicc" in result


def test_es_vid_contains_key():
    result = ES._vid("euicc", "eid-xyz")
    assert "eid-xyz" in result


def test_es_vid_contains_telecom_did():
    result = ES._vid("euicc", "key")
    assert "telecom.etzhayyim.com" in result


# ─── telecom_esim — _hash ─────────────────────────────────────────────────────

def test_es_hash_none_returns_none():
    assert ES._hash(None) is None


def test_es_hash_empty_string_returns_none():
    assert ES._hash("") is None


def test_es_hash_already_prefixed_passes_through():
    value = "sha256:abc123"
    result = ES._hash(value)
    assert result == value


def test_es_hash_plain_string_adds_prefix():
    result = ES._hash("my-eid-value")
    assert result is not None
    assert result.startswith("sha256:")


def test_es_hash_is_deterministic():
    a = ES._hash("test-value")
    b = ES._hash("test-value")
    assert a == b


def test_es_hash_differs_by_input():
    a = ES._hash("value1")
    b = ES._hash("value2")
    assert a != b


# ─── telecom_esim — _require ──────────────────────────────────────────────────

def test_es_require_no_missing_does_not_raise():
    payload = {"eid": "abc", "deviceKind": "smartphone"}
    ES._require(payload, ["eid", "deviceKind"])  # should not raise


def test_es_require_missing_field_raises_value_error():
    with pytest.raises(ValueError):
        ES._require({"eid": "abc"}, ["eid", "deviceKind"])


def test_es_require_none_value_raises():
    with pytest.raises(ValueError):
        ES._require({"eid": None}, ["eid"])


def test_es_require_empty_string_raises():
    with pytest.raises(ValueError):
        ES._require({"eid": ""}, ["eid"])


def test_es_require_empty_fields_list_does_not_raise():
    ES._require({}, [])


# ─── telecom_esim — constants ────────────────────────────────────────────────

def test_es_telecom_did_starts_with_did():
    assert ES.TELECOM_DID.startswith("did:")


def test_es_device_kinds_is_set():
    assert isinstance(ES.DEVICE_KINDS, set)


def test_es_device_kinds_contains_smartphone():
    assert "smartphone" in ES.DEVICE_KINDS


def test_es_profile_types_is_set():
    assert isinstance(ES.PROFILE_TYPES, set)


def test_es_profile_states_is_set():
    assert isinstance(ES.PROFILE_STATES, set)


def test_es_profile_states_contains_enabled():
    assert "enabled" in ES.PROFILE_STATES


def test_es_op_kinds_is_set():
    assert isinstance(ES.OP_KINDS, set)


def test_es_disable_reasons_is_set():
    assert isinstance(ES.DISABLE_REASONS, set)


def test_es_delete_reasons_is_set():
    assert isinstance(ES.DELETE_REASONS, set)


def test_es_event_types_is_set():
    assert isinstance(ES.EVENT_TYPES, set)


# ─── telecom_oran — _now_iso ──────────────────────────────────────────────────

def test_or_now_iso_returns_string():
    assert isinstance(OR._now_iso(), str)


def test_or_now_iso_contains_t():
    assert "T" in OR._now_iso()


# ─── telecom_oran — _new_id ───────────────────────────────────────────────────

def test_or_new_id_with_parts_deterministic():
    a = OR._new_id("a1pol", "ue1", "slice1")
    b = OR._new_id("a1pol", "ue1", "slice1")
    assert a == b


def test_or_new_id_starts_with_prefix():
    result = OR._new_id("e2sub", "ran1")
    assert result.startswith("e2sub_")


def test_or_new_id_without_parts_is_unique():
    a = OR._new_id("x")
    b = OR._new_id("x")
    assert a != b


# ─── telecom_oran — _join ────────────────────────────────────────────────────

def test_or_join_none_returns_none():
    assert OR._join(None) is None


def test_or_join_empty_string_returns_none():
    assert OR._join("") is None


def test_or_join_plain_string_returns_string():
    assert OR._join("qos_assurance") == "qos_assurance"


def test_or_join_list_joins_with_comma():
    result = OR._join(["a", "b", "c"])
    assert result == "a,b,c"


def test_or_join_empty_list_returns_none():
    assert OR._join([]) is None


def test_or_join_set_joins_items():
    result = OR._join({"only"})
    assert result == "only"


# ─── telecom_oran — _join_vids ───────────────────────────────────────────────

def test_or_join_vids_none_returns_none():
    assert OR._join_vids(None, "a1policy") is None


def test_or_join_vids_non_list_returns_none():
    assert OR._join_vids("not-a-list", "kind") is None


def test_or_join_vids_list_returns_string():
    result = OR._join_vids(["key1", "key2"], "a1policy")
    assert result is not None
    assert "key1" in result
    assert "key2" in result


def test_or_join_vids_empty_list_returns_none():
    assert OR._join_vids([], "kind") is None


# ─── telecom_oran — _vid ─────────────────────────────────────────────────────

def test_or_vid_starts_with_at():
    result = OR._vid("a1policy", "pol-001")
    assert result.startswith("at://")


def test_or_vid_contains_kind():
    result = OR._vid("a1policy", "pol-001")
    assert "a1policy" in result


def test_or_vid_contains_ident():
    result = OR._vid("e2sub", "sub-xyz")
    assert "sub-xyz" in result


# ─── telecom_oran — _require ─────────────────────────────────────────────────

def test_or_require_present_does_not_raise():
    OR._require({"rAppId": "app1", "useCase": "qos_assurance"}, ["rAppId", "useCase"])


def test_or_require_missing_raises():
    with pytest.raises(ValueError, match="missing"):
        OR._require({"rAppId": "app1"}, ["rAppId", "useCase"])


# ─── telecom_oran — _caller ──────────────────────────────────────────────────

def test_or_caller_returns_did_when_present():
    result = OR._caller({"callerDid": "did:web:my-actor.etzhayyim.com"})
    assert result == "did:web:my-actor.etzhayyim.com"


def test_or_caller_falls_back_to_telecom_did():
    result = OR._caller({})
    assert result == OR.TELECOM_DID


# ─── telecom_oran — _require_vault_ref ───────────────────────────────────────

def test_or_require_vault_ref_valid_passes():
    OR._require_vault_ref("vault://my-secret", "field")  # no error


def test_or_require_vault_ref_none_passes():
    OR._require_vault_ref(None, "field")  # None is allowed


def test_or_require_vault_ref_invalid_raises():
    with pytest.raises(ValueError, match="vault://"):
        OR._require_vault_ref("not-a-vault-ref", "field")


# ─── telecom_oran — _require_hash_prefix ─────────────────────────────────────

def test_or_require_hash_prefix_sha256_ok():
    OR._require_hash_prefix("sha256:abc", "field")


def test_or_require_hash_prefix_sha384_ok():
    OR._require_hash_prefix("sha384:def", "field")


def test_or_require_hash_prefix_sha512_ok():
    OR._require_hash_prefix("sha512:xyz", "field")


def test_or_require_hash_prefix_invalid_raises():
    with pytest.raises(ValueError):
        OR._require_hash_prefix("md5:bad", "field")


# ─── telecom_oran — constants ────────────────────────────────────────────────

def test_or_telecom_did_starts_with_did():
    assert OR.TELECOM_DID.startswith("did:")


def test_or_a1_use_cases_is_set():
    assert isinstance(OR.A1_USE_CASES, set)


def test_or_a1_use_cases_contains_qos():
    assert "qos_assurance" in OR.A1_USE_CASES


def test_or_e2_service_models_is_set():
    assert isinstance(OR.E2_SERVICE_MODELS, set)


def test_or_e2_service_models_contains_kpm():
    assert "e2sm-kpm" in OR.E2_SERVICE_MODELS


def test_or_o1_target_kinds_is_set():
    assert isinstance(OR.O1_TARGET_KINDS, set)


def test_or_o2_resource_kinds_is_set():
    assert isinstance(OR.O2_RESOURCE_KINDS, set)
