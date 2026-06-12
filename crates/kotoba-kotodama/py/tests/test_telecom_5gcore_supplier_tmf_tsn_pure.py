"""Pure helper tests for telecom_5gcore, telecom_supplier, telecom_tmf,
and telecom_tsn primitives.

Covers pure functions with no DB/Zeebe dependencies:
- telecom_5gcore: _now_iso / _hash_id / _new_id / _join / _vid /
                  _require / _caller / TELECOM_DID / NF_TYPES /
                  AUTH_METHODS / AUTH_RESULTS / SESSION_TYPES
- telecom_supplier: _now_iso / _hash_id / _new_id / _parse_date /
                    _join / _vid / _require / _caller / TELECOM_DID /
                    PEER_KINDS / TAP_FILE_TYPES / USAGE_TYPES
- telecom_tmf: _now_iso / _new_id / _vid / _hash_pii / _join /
               _require / TELECOM_DID / ORDER_KINDS_PRODUCT /
               LIFECYCLE_STATUS_PRODUCT_OFFERING / PAYMENT_METHOD_KINDS
- telecom_tsn: _now_iso / _hash_id / _new_id / _join / _join_vids /
               _require / TELECOM_DID / PROFILE_KINDS / SHAPER_KINDS /
               SEVERITIES / DEFAULT_SYNC_OFFSET_BREACH_NS
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import telecom_5gcore as G5C
from kotodama.primitives import telecom_supplier as SUP
from kotodama.primitives import telecom_tmf as TMF
from kotodama.primitives import telecom_tsn as TSN


# ─── telecom_5gcore — _now_iso ───────────────────────────────────────────────

def test_5gc_now_iso_returns_string():
    assert isinstance(G5C._now_iso(), str)


def test_5gc_now_iso_contains_t():
    assert "T" in G5C._now_iso()


# ─── telecom_5gcore — _hash_id ───────────────────────────────────────────────

def test_5gc_hash_id_none_returns_none():
    assert G5C._hash_id(None) is None


def test_5gc_hash_id_empty_returns_none():
    assert G5C._hash_id("") is None


def test_5gc_hash_id_adds_sha256_prefix():
    result = G5C._hash_id("supi-001")
    assert result is not None
    assert result.startswith("sha256:")


def test_5gc_hash_id_deterministic():
    a = G5C._hash_id("supi-001")
    b = G5C._hash_id("supi-001")
    assert a == b


# ─── telecom_5gcore — _new_id ────────────────────────────────────────────────

def test_5gc_new_id_with_parts_deterministic():
    a = G5C._new_id("pduSess", "amf-1", "ue-001")
    b = G5C._new_id("pduSess", "amf-1", "ue-001")
    assert a == b


def test_5gc_new_id_starts_with_prefix():
    result = G5C._new_id("auth", "ue-1")
    assert result.startswith("auth_")


def test_5gc_new_id_without_parts_unique():
    a = G5C._new_id("pduSess")
    b = G5C._new_id("pduSess")
    assert a != b


# ─── telecom_5gcore — _join ──────────────────────────────────────────────────

def test_5gc_join_none_returns_none():
    assert G5C._join(None) is None


def test_5gc_join_plain_string():
    assert G5C._join("AMF") == "AMF"


def test_5gc_join_list_joins():
    result = G5C._join(["AMF", "SMF"])
    assert result == "AMF,SMF"


def test_5gc_join_empty_list_returns_none():
    assert G5C._join([]) is None


# ─── telecom_5gcore — _vid ───────────────────────────────────────────────────

def test_5gc_vid_starts_with_at():
    result = G5C._vid("pduSession", "sess-001")
    assert result.startswith("at://")


def test_5gc_vid_contains_kind():
    result = G5C._vid("authEvent", "evt-1")
    assert "authEvent" in result


def test_5gc_vid_contains_ident():
    result = G5C._vid("pduSession", "sess-xyz")
    assert "sess-xyz" in result


# ─── telecom_5gcore — _require ───────────────────────────────────────────────

def test_5gc_require_present_does_not_raise():
    G5C._require({"supi": "s1", "authMethod": "5G-AKA"}, ["supi", "authMethod"])


def test_5gc_require_missing_raises():
    with pytest.raises(ValueError):
        G5C._require({"supi": "s1"}, ["supi", "authMethod"])


# ─── telecom_5gcore — _caller ────────────────────────────────────────────────

def test_5gc_caller_uses_caller_did():
    result = G5C._caller({"callerDid": "did:web:amf.etzhayyim.com"})
    assert result == "did:web:amf.etzhayyim.com"


def test_5gc_caller_falls_back_to_telecom_did():
    result = G5C._caller({})
    assert result == G5C.TELECOM_DID


# ─── telecom_5gcore — constants ──────────────────────────────────────────────

def test_5gc_telecom_did_starts_with_did():
    assert G5C.TELECOM_DID.startswith("did:")


def test_5gc_nf_types_is_set():
    assert isinstance(G5C.NF_TYPES, set)


def test_5gc_nf_types_contains_amf():
    assert "AMF" in G5C.NF_TYPES


def test_5gc_auth_methods_is_set():
    assert isinstance(G5C.AUTH_METHODS, set)


def test_5gc_auth_methods_contains_5g_aka():
    assert "5G-AKA" in G5C.AUTH_METHODS


def test_5gc_auth_results_is_set():
    assert isinstance(G5C.AUTH_RESULTS, set)


def test_5gc_session_types_is_set():
    assert isinstance(G5C.SESSION_TYPES, set)


def test_5gc_charging_methods_is_set():
    assert isinstance(G5C.CHARGING_METHODS, set)


# ─── telecom_supplier — _now_iso ─────────────────────────────────────────────

def test_sup_now_iso_returns_string():
    assert isinstance(SUP._now_iso(), str)


def test_sup_now_iso_contains_t():
    assert "T" in SUP._now_iso()


# ─── telecom_supplier — _hash_id ─────────────────────────────────────────────

def test_sup_hash_id_none_returns_none():
    assert SUP._hash_id(None) is None


def test_sup_hash_id_empty_returns_none():
    assert SUP._hash_id("") is None


def test_sup_hash_id_adds_sha256_prefix():
    result = SUP._hash_id("msisdn-001")
    assert result is not None
    assert result.startswith("sha256:")


def test_sup_hash_id_deterministic():
    a = SUP._hash_id("msisdn-001")
    b = SUP._hash_id("msisdn-001")
    assert a == b


# ─── telecom_supplier — _new_id ──────────────────────────────────────────────

def test_sup_new_id_with_parts_deterministic():
    a = SUP._new_id("inter", "plmn-001", "plmn-002")
    b = SUP._new_id("inter", "plmn-001", "plmn-002")
    assert a == b


def test_sup_new_id_starts_with_prefix():
    result = SUP._new_id("tap", "file-1")
    assert result.startswith("tap_")


def test_sup_new_id_without_parts_unique():
    a = SUP._new_id("inter")
    b = SUP._new_id("inter")
    assert a != b


# ─── telecom_supplier — _parse_date ──────────────────────────────────────────

def test_sup_parse_date_iso_string():
    result = SUP._parse_date("2026-04-29", "startDate")
    assert isinstance(result, date)
    assert result.year == 2026


def test_sup_parse_date_with_time():
    result = SUP._parse_date("2026-04-29T12:00:00Z", "startDate")
    assert result.year == 2026
    assert result.month == 4


def test_sup_parse_date_date_object_passes_through():
    d = date(2026, 1, 1)
    result = SUP._parse_date(d, "startDate")
    assert result == d


def test_sup_parse_date_empty_raises():
    with pytest.raises(ValueError):
        SUP._parse_date("", "startDate")


def test_sup_parse_date_none_raises():
    with pytest.raises(ValueError):
        SUP._parse_date(None, "startDate")


# ─── telecom_supplier — _vid ─────────────────────────────────────────────────

def test_sup_vid_starts_with_at():
    result = SUP._vid("interConnect", "ic-001")
    assert result.startswith("at://")


def test_sup_vid_contains_kind():
    result = SUP._vid("tapFile", "file-1")
    assert "tapFile" in result


# ─── telecom_supplier — _require ─────────────────────────────────────────────

def test_sup_require_present_does_not_raise():
    SUP._require({"peerId": "p1", "peerKind": "mno"}, ["peerId", "peerKind"])


def test_sup_require_missing_raises():
    with pytest.raises(ValueError):
        SUP._require({"peerId": "p1"}, ["peerId", "peerKind"])


# ─── telecom_supplier — _caller ──────────────────────────────────────────────

def test_sup_caller_uses_caller_did():
    result = SUP._caller({"callerDid": "did:web:mno.etzhayyim.com"})
    assert result == "did:web:mno.etzhayyim.com"


def test_sup_caller_falls_back_to_telecom_did():
    result = SUP._caller({})
    assert result == SUP.TELECOM_DID


# ─── telecom_supplier — constants ────────────────────────────────────────────

def test_sup_telecom_did_starts_with_did():
    assert SUP.TELECOM_DID.startswith("did:")


def test_sup_peer_kinds_is_set():
    assert isinstance(SUP.PEER_KINDS, set)


def test_sup_peer_kinds_contains_mno():
    assert "mno" in SUP.PEER_KINDS


def test_sup_tap_file_types_is_set():
    assert isinstance(SUP.TAP_FILE_TYPES, set)


def test_sup_tap_file_types_contains_tap():
    assert "tap" in SUP.TAP_FILE_TYPES


def test_sup_usage_types_is_set():
    assert isinstance(SUP.USAGE_TYPES, set)


# ─── telecom_tmf — _now_iso ──────────────────────────────────────────────────

def test_tmf_now_iso_returns_string():
    assert isinstance(TMF._now_iso(), str)


def test_tmf_now_iso_contains_t():
    assert "T" in TMF._now_iso()


# ─── telecom_tmf — _new_id ───────────────────────────────────────────────────

def test_tmf_new_id_with_parts_deterministic():
    a = TMF._new_id("order", "customer-1", "product-A")
    b = TMF._new_id("order", "customer-1", "product-A")
    assert a == b


def test_tmf_new_id_starts_with_prefix():
    result = TMF._new_id("svc", "order-1")
    assert result.startswith("svc_")


def test_tmf_new_id_without_parts_unique():
    a = TMF._new_id("order")
    b = TMF._new_id("order")
    assert a != b


# ─── telecom_tmf — _vid ──────────────────────────────────────────────────────

def test_tmf_vid_starts_with_at():
    result = TMF._vid("productOrder", "ord-001")
    assert result.startswith("at://")


def test_tmf_vid_contains_kind():
    result = TMF._vid("serviceOrder", "so-1")
    assert "serviceOrder" in result


def test_tmf_vid_contains_key():
    result = TMF._vid("productOrder", "ord-xyz")
    assert "ord-xyz" in result


# ─── telecom_tmf — _hash_pii ─────────────────────────────────────────────────

def test_tmf_hash_pii_none_returns_none():
    assert TMF._hash_pii(None) is None


def test_tmf_hash_pii_empty_returns_none():
    assert TMF._hash_pii("") is None


def test_tmf_hash_pii_adds_sha256_prefix():
    result = TMF._hash_pii("customer-email@example.com")
    assert result is not None
    assert result.startswith("sha256:")


def test_tmf_hash_pii_deterministic():
    a = TMF._hash_pii("email@example.com")
    b = TMF._hash_pii("email@example.com")
    assert a == b


# ─── telecom_tmf — _join ─────────────────────────────────────────────────────

def test_tmf_join_none_returns_none():
    assert TMF._join(None) is None


def test_tmf_join_plain_string():
    assert TMF._join("add") == "add"


def test_tmf_join_list_joins():
    result = TMF._join(["add", "modify"])
    assert result == "add,modify"


def test_tmf_join_empty_list_returns_none():
    assert TMF._join([]) is None


# ─── telecom_tmf — _require ──────────────────────────────────────────────────

def test_tmf_require_present_does_not_raise():
    TMF._require({"customerId": "c1", "orderKind": "add"}, ["customerId", "orderKind"])


def test_tmf_require_missing_raises():
    with pytest.raises(ValueError):
        TMF._require({"customerId": "c1"}, ["customerId", "orderKind"])


# ─── telecom_tmf — constants ─────────────────────────────────────────────────

def test_tmf_telecom_did_starts_with_did():
    assert TMF.TELECOM_DID.startswith("did:")


def test_tmf_lifecycle_status_product_offering_is_set():
    assert isinstance(TMF.LIFECYCLE_STATUS_PRODUCT_OFFERING, set)


def test_tmf_order_kinds_product_is_set():
    assert isinstance(TMF.ORDER_KINDS_PRODUCT, set)


def test_tmf_order_kinds_product_contains_add():
    assert "add" in TMF.ORDER_KINDS_PRODUCT


def test_tmf_payment_method_kinds_is_set():
    assert isinstance(TMF.PAYMENT_METHOD_KINDS, set)


def test_tmf_customer_kinds_is_set():
    assert isinstance(TMF.CUSTOMER_KINDS, set)


def test_tmf_account_kinds_is_set():
    assert isinstance(TMF.ACCOUNT_KINDS, set)


# ─── telecom_tsn — _now_iso ──────────────────────────────────────────────────

def test_tsn_now_iso_returns_string():
    assert isinstance(TSN._now_iso(), str)


def test_tsn_now_iso_contains_t():
    assert "T" in TSN._now_iso()


# ─── telecom_tsn — _hash_id ──────────────────────────────────────────────────

def test_tsn_hash_id_none_returns_none():
    assert TSN._hash_id(None) is None


def test_tsn_hash_id_empty_returns_none():
    assert TSN._hash_id("") is None


def test_tsn_hash_id_adds_sha256_prefix():
    result = TSN._hash_id("device-mac-001")
    assert result is not None
    assert result.startswith("sha256:")


# ─── telecom_tsn — _new_id ───────────────────────────────────────────────────

def test_tsn_new_id_with_parts_deterministic():
    a = TSN._new_id("stream", "talker-1", "listener-1")
    b = TSN._new_id("stream", "talker-1", "listener-1")
    assert a == b


def test_tsn_new_id_starts_with_prefix():
    result = TSN._new_id("bridge", "node-1")
    assert result.startswith("bridge_")


def test_tsn_new_id_without_parts_unique():
    a = TSN._new_id("stream")
    b = TSN._new_id("stream")
    assert a != b


# ─── telecom_tsn — _join ─────────────────────────────────────────────────────

def test_tsn_join_none_returns_none():
    assert TSN._join(None) is None


def test_tsn_join_plain_string():
    assert TSN._join("cbs") == "cbs"


def test_tsn_join_list_joins():
    result = TSN._join(["cbs", "tas"])
    assert result == "cbs,tas"


def test_tsn_join_empty_list_returns_none():
    assert TSN._join([]) is None


# ─── telecom_tsn — _join_vids ────────────────────────────────────────────────

def test_tsn_join_vids_none_returns_none():
    assert TSN._join_vids(None, "bridge") is None


def test_tsn_join_vids_non_list_returns_none():
    assert TSN._join_vids("not-list", "bridge") is None


def test_tsn_join_vids_empty_list_returns_none():
    assert TSN._join_vids([], "bridge") is None


def test_tsn_join_vids_list_returns_string():
    result = TSN._join_vids(["key1", "key2"], "bridge")
    assert result is not None
    assert "key1" in result


# ─── telecom_tsn — _require ──────────────────────────────────────────────────

def test_tsn_require_present_does_not_raise():
    TSN._require({"streamId": "s1", "profileKind": "industrial_iec_iet"}, ["streamId", "profileKind"])


def test_tsn_require_missing_raises():
    with pytest.raises(ValueError):
        TSN._require({"streamId": "s1"}, ["streamId", "profileKind"])


# ─── telecom_tsn — constants ─────────────────────────────────────────────────

def test_tsn_telecom_did_starts_with_did():
    assert TSN.TELECOM_DID.startswith("did:")


def test_tsn_profile_kinds_is_set():
    assert isinstance(TSN.PROFILE_KINDS, set)


def test_tsn_shaper_kinds_is_set():
    assert isinstance(TSN.SHAPER_KINDS, set)


def test_tsn_shaper_kinds_contains_cbs():
    assert "cbs" in TSN.SHAPER_KINDS


def test_tsn_severities_is_set():
    assert isinstance(TSN.SEVERITIES, set)


def test_tsn_severities_contains_critical():
    assert "critical" in TSN.SEVERITIES


def test_tsn_default_sync_offset_is_positive_int():
    assert isinstance(TSN.DEFAULT_SYNC_OFFSET_BREACH_NS, int)
    assert TSN.DEFAULT_SYNC_OFFSET_BREACH_NS > 0


def test_tsn_breach_kinds_is_set():
    assert isinstance(TSN.BREACH_KINDS, set)


def test_tsn_reservation_kinds_is_set():
    assert isinstance(TSN.RESERVATION_KINDS, set)
