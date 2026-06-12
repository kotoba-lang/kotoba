"""Pure helper tests for telecom_5g_security, telecom_optical, telecom_mec,
and telecom_nfv primitives.

Covers pure functions with no DB/Zeebe dependencies:
- telecom_5g_security: _now_iso / _hash_id / _new_id / _join / _vid /
                       _require / _caller / _require_vault_ref /
                       _require_hash_prefix / TELECOM_DID /
                       ANALYTICS_IDS / NF_TYPES / SECURITY_RESULTS /
                       ROTATION_REASONS / N32_CIPHER_SUITES
- telecom_optical: _now_iso / _new_id / _join / _join_vids / _vid /
                   _require / _caller / TELECOM_DID /
                   MODULATIONS / FIBER_TYPES / FEC_KINDS / SEVERITIES
- telecom_mec: _now_iso / _new_id / _join / _vid / _require / _caller /
               _require_vault_ref / _require_hash_prefix / TELECOM_DID /
               LATENCY_CLASSES / ACR_MODES / FEDERATION_KINDS
- telecom_nfv: _now_iso / _new_id / _join / _vid / _require / _caller /
               _require_vault_ref / _require_hash_prefix / TELECOM_DID /
               DESCRIPTOR_FORMATS / VNF_KINDS / SCALE_KINDS /
               SOUTHBOUND_PROTOCOLS
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import telecom_5g_security as G5
from kotodama.primitives import telecom_optical as OPT
from kotodama.primitives import telecom_mec as MEC
from kotodama.primitives import telecom_nfv as NFV


# ─── telecom_5g_security — _now_iso ──────────────────────────────────────────

def test_g5_now_iso_returns_string():
    assert isinstance(G5._now_iso(), str)


def test_g5_now_iso_contains_t():
    assert "T" in G5._now_iso()


# ─── telecom_5g_security — _hash_id ──────────────────────────────────────────

def test_g5_hash_id_none_returns_none():
    assert G5._hash_id(None) is None


def test_g5_hash_id_empty_returns_none():
    assert G5._hash_id("") is None


def test_g5_hash_id_whitespace_returns_none():
    assert G5._hash_id("   ") is None


def test_g5_hash_id_adds_sha256_prefix():
    result = G5._hash_id("imsi-001")
    assert result is not None
    assert result.startswith("sha256:")


def test_g5_hash_id_deterministic():
    a = G5._hash_id("imsi-001")
    b = G5._hash_id("imsi-001")
    assert a == b


def test_g5_hash_id_differs_by_value():
    a = G5._hash_id("imsi-001")
    b = G5._hash_id("imsi-002")
    assert a != b


def test_g5_hash_id_int_input():
    result = G5._hash_id(12345)
    assert result is not None
    assert result.startswith("sha256:")


# ─── telecom_5g_security — _new_id ───────────────────────────────────────────

def test_g5_new_id_with_parts_deterministic():
    a = G5._new_id("sepp", "plmn-001", "ipx-001")
    b = G5._new_id("sepp", "plmn-001", "ipx-001")
    assert a == b


def test_g5_new_id_starts_with_prefix():
    result = G5._new_id("n32", "chan-1")
    assert result.startswith("n32_")


def test_g5_new_id_without_parts_unique():
    a = G5._new_id("sepp")
    b = G5._new_id("sepp")
    assert a != b


# ─── telecom_5g_security — _join ─────────────────────────────────────────────

def test_g5_join_none_returns_none():
    assert G5._join(None) is None


def test_g5_join_empty_string_returns_none():
    assert G5._join("") is None


def test_g5_join_plain_string():
    assert G5._join("nrf") == "nrf"


def test_g5_join_list_joins():
    result = G5._join(["AMF", "SMF", "UPF"])
    assert result == "AMF,SMF,UPF"


def test_g5_join_empty_list_returns_none():
    assert G5._join([]) is None


# ─── telecom_5g_security — _vid ──────────────────────────────────────────────

def test_g5_vid_starts_with_at():
    result = G5._vid("seppSession", "sess-001")
    assert result.startswith("at://")


def test_g5_vid_contains_kind():
    result = G5._vid("seppSession", "sess-001")
    assert "seppSession" in result


def test_g5_vid_contains_ident():
    result = G5._vid("n32Channel", "chan-xyz")
    assert "chan-xyz" in result


# ─── telecom_5g_security — _require ──────────────────────────────────────────

def test_g5_require_present_does_not_raise():
    G5._require({"seppId": "s1", "plmnId": "001"}, ["seppId", "plmnId"])


def test_g5_require_missing_raises():
    with pytest.raises(ValueError):
        G5._require({"seppId": "s1"}, ["seppId", "plmnId"])


def test_g5_require_none_raises():
    with pytest.raises(ValueError):
        G5._require({"seppId": None}, ["seppId"])


# ─── telecom_5g_security — _caller ───────────────────────────────────────────

def test_g5_caller_uses_caller_did():
    result = G5._caller({"callerDid": "did:web:nrf.etzhayyim.com"})
    assert result == "did:web:nrf.etzhayyim.com"


def test_g5_caller_falls_back_to_telecom_did():
    result = G5._caller({})
    assert result == G5.TELECOM_DID


# ─── telecom_5g_security — _require_vault_ref ────────────────────────────────

def test_g5_require_vault_ref_valid_passes():
    G5._require_vault_ref("vault://my-cert", "cert")


def test_g5_require_vault_ref_none_passes():
    G5._require_vault_ref(None, "cert")


def test_g5_require_vault_ref_invalid_raises():
    with pytest.raises(ValueError):
        G5._require_vault_ref("not-a-vault", "cert")


# ─── telecom_5g_security — _require_hash_prefix ──────────────────────────────

def test_g5_require_hash_prefix_sha256_ok():
    G5._require_hash_prefix("sha256:abc", "field")


def test_g5_require_hash_prefix_sha512_ok():
    G5._require_hash_prefix("sha512:xyz", "field")


def test_g5_require_hash_prefix_invalid_raises():
    with pytest.raises(ValueError):
        G5._require_hash_prefix("md5:bad", "field")


# ─── telecom_5g_security — constants ─────────────────────────────────────────

def test_g5_telecom_did_starts_with_did():
    assert G5.TELECOM_DID.startswith("did:")


def test_g5_analytics_ids_is_set():
    assert isinstance(G5.ANALYTICS_IDS, set)


def test_g5_analytics_ids_not_empty():
    assert len(G5.ANALYTICS_IDS) > 0


def test_g5_nf_types_is_set():
    assert isinstance(G5.NF_TYPES, set)


def test_g5_nf_types_contains_amf():
    assert "AMF" in G5.NF_TYPES


def test_g5_nf_types_contains_smf():
    assert "SMF" in G5.NF_TYPES


def test_g5_security_results_is_set():
    assert isinstance(G5.SECURITY_RESULTS, set)


def test_g5_security_results_contains_verified():
    assert "verified" in G5.SECURITY_RESULTS


def test_g5_rotation_reasons_is_set():
    assert isinstance(G5.ROTATION_REASONS, set)


def test_g5_n32_cipher_suites_is_set():
    assert isinstance(G5.N32_CIPHER_SUITES, set)


def test_g5_n32_channels_is_set():
    assert isinstance(G5.N32_CHANNELS, set)


# ─── telecom_optical — _now_iso ──────────────────────────────────────────────

def test_opt_now_iso_returns_string():
    assert isinstance(OPT._now_iso(), str)


def test_opt_now_iso_contains_t():
    assert "T" in OPT._now_iso()


# ─── telecom_optical — _new_id ───────────────────────────────────────────────

def test_opt_new_id_with_parts_deterministic():
    a = OPT._new_id("ols", "roadm-a", "roadm-b")
    b = OPT._new_id("ols", "roadm-a", "roadm-b")
    assert a == b


def test_opt_new_id_starts_with_prefix():
    result = OPT._new_id("dwdm", "chan-1")
    assert result.startswith("dwdm_")


def test_opt_new_id_without_parts_unique():
    a = OPT._new_id("ols")
    b = OPT._new_id("ols")
    assert a != b


# ─── telecom_optical — _join ─────────────────────────────────────────────────

def test_opt_join_none_returns_none():
    assert OPT._join(None) is None


def test_opt_join_empty_string_returns_none():
    assert OPT._join("") is None


def test_opt_join_list_joins():
    result = OPT._join(["qpsk", "16qam"])
    assert result == "qpsk,16qam"


def test_opt_join_set_single_item():
    result = OPT._join({"only"})
    assert result == "only"


def test_opt_join_empty_list_returns_none():
    assert OPT._join([]) is None


# ─── telecom_optical — _join_vids ────────────────────────────────────────────

def test_opt_join_vids_none_returns_none():
    assert OPT._join_vids(None, "ols") is None


def test_opt_join_vids_non_list_returns_none():
    assert OPT._join_vids("not-list", "ols") is None


def test_opt_join_vids_empty_list_returns_none():
    assert OPT._join_vids([], "ols") is None


def test_opt_join_vids_list_returns_string():
    result = OPT._join_vids(["key1", "key2"], "ols")
    assert result is not None
    assert "key1" in result
    assert "key2" in result


# ─── telecom_optical — _vid ──────────────────────────────────────────────────

def test_opt_vid_starts_with_at():
    result = OPT._vid("ols", "ols-001")
    assert result.startswith("at://")


def test_opt_vid_contains_kind():
    result = OPT._vid("dwdmChannel", "ch-1")
    assert "dwdmChannel" in result


def test_opt_vid_contains_ident():
    result = OPT._vid("roadm", "node-xyz")
    assert "node-xyz" in result


# ─── telecom_optical — _require ──────────────────────────────────────────────

def test_opt_require_present_does_not_raise():
    OPT._require({"olsId": "ols-1", "modulation": "qpsk"}, ["olsId", "modulation"])


def test_opt_require_missing_raises():
    with pytest.raises(ValueError):
        OPT._require({"olsId": "ols-1"}, ["olsId", "modulation"])


# ─── telecom_optical — _caller ───────────────────────────────────────────────

def test_opt_caller_uses_caller_did():
    result = OPT._caller({"callerDid": "did:web:pce.etzhayyim.com"})
    assert result == "did:web:pce.etzhayyim.com"


def test_opt_caller_falls_back_to_telecom_did():
    result = OPT._caller({})
    assert result == OPT.TELECOM_DID


# ─── telecom_optical — constants ─────────────────────────────────────────────

def test_opt_telecom_did_starts_with_did():
    assert OPT.TELECOM_DID.startswith("did:")


def test_opt_modulations_is_set():
    assert isinstance(OPT.MODULATIONS, set)


def test_opt_modulations_contains_qpsk():
    assert "qpsk" in OPT.MODULATIONS


def test_opt_fiber_types_is_set():
    assert isinstance(OPT.FIBER_TYPES, set)


def test_opt_fiber_types_contains_smf28():
    assert "smf28" in OPT.FIBER_TYPES


def test_opt_fec_kinds_is_set():
    assert isinstance(OPT.FEC_KINDS, set)


def test_opt_severities_is_set():
    assert isinstance(OPT.SEVERITIES, set)


def test_opt_severities_contains_critical():
    assert "critical" in OPT.SEVERITIES


def test_opt_roadm_kinds_is_set():
    assert isinstance(OPT.ROADM_KINDS, set)


# ─── telecom_mec — _now_iso ──────────────────────────────────────────────────

def test_mec_now_iso_returns_string():
    assert isinstance(MEC._now_iso(), str)


def test_mec_now_iso_contains_t():
    assert "T" in MEC._now_iso()


# ─── telecom_mec — _new_id ───────────────────────────────────────────────────

def test_mec_new_id_with_parts_deterministic():
    a = MEC._new_id("meHost", "site-a", "zone-1")
    b = MEC._new_id("meHost", "site-a", "zone-1")
    assert a == b


def test_mec_new_id_starts_with_prefix():
    result = MEC._new_id("appInst", "app-1")
    assert result.startswith("appInst_")


def test_mec_new_id_without_parts_unique():
    a = MEC._new_id("meHost")
    b = MEC._new_id("meHost")
    assert a != b


# ─── telecom_mec — _join ─────────────────────────────────────────────────────

def test_mec_join_none_returns_none():
    assert MEC._join(None) is None


def test_mec_join_plain_string():
    assert MEC._join("urllc") == "urllc"


def test_mec_join_list_joins():
    result = MEC._join(["urllc", "embb"])
    assert result == "urllc,embb"


def test_mec_join_empty_list_returns_none():
    assert MEC._join([]) is None


# ─── telecom_mec — _vid ──────────────────────────────────────────────────────

def test_mec_vid_starts_with_at():
    result = MEC._vid("meHost", "host-001")
    assert result.startswith("at://")


def test_mec_vid_contains_kind():
    result = MEC._vid("appInstance", "inst-1")
    assert "appInstance" in result


def test_mec_vid_contains_ident():
    result = MEC._vid("meHost", "host-xyz")
    assert "host-xyz" in result


# ─── telecom_mec — _require ──────────────────────────────────────────────────

def test_mec_require_present_does_not_raise():
    MEC._require({"meHostId": "h1", "latencyClass": "urllc"}, ["meHostId", "latencyClass"])


def test_mec_require_missing_raises():
    with pytest.raises(ValueError):
        MEC._require({"meHostId": "h1"}, ["meHostId", "latencyClass"])


# ─── telecom_mec — _caller ───────────────────────────────────────────────────

def test_mec_caller_uses_caller_did():
    result = MEC._caller({"callerDid": "did:web:mec.etzhayyim.com"})
    assert result == "did:web:mec.etzhayyim.com"


def test_mec_caller_falls_back_to_telecom_did():
    result = MEC._caller({})
    assert result == MEC.TELECOM_DID


# ─── telecom_mec — _require_vault_ref ────────────────────────────────────────

def test_mec_require_vault_ref_valid_passes():
    MEC._require_vault_ref("vault://mec-key", "key")


def test_mec_require_vault_ref_none_passes():
    MEC._require_vault_ref(None, "key")


def test_mec_require_vault_ref_invalid_raises():
    with pytest.raises(ValueError):
        MEC._require_vault_ref("plain-key", "key")


# ─── telecom_mec — _require_hash_prefix ──────────────────────────────────────

def test_mec_require_hash_prefix_sha384_ok():
    MEC._require_hash_prefix("sha384:abc", "field")


def test_mec_require_hash_prefix_invalid_raises():
    with pytest.raises(ValueError):
        MEC._require_hash_prefix("md5:bad", "field")


# ─── telecom_mec — constants ─────────────────────────────────────────────────

def test_mec_telecom_did_starts_with_did():
    assert MEC.TELECOM_DID.startswith("did:")


def test_mec_latency_classes_is_set():
    assert isinstance(MEC.LATENCY_CLASSES, set)


def test_mec_latency_classes_contains_urllc():
    assert "urllc" in MEC.LATENCY_CLASSES


def test_mec_acr_modes_is_set():
    assert isinstance(MEC.ACR_MODES, set)


def test_mec_federation_kinds_is_set():
    assert isinstance(MEC.FEDERATION_KINDS, set)


def test_mec_relocation_triggers_is_set():
    assert isinstance(MEC.RELOCATION_TRIGGERS, set)


# ─── telecom_nfv — _now_iso ──────────────────────────────────────────────────

def test_nfv_now_iso_returns_string():
    assert isinstance(NFV._now_iso(), str)


def test_nfv_now_iso_contains_t():
    assert "T" in NFV._now_iso()


# ─── telecom_nfv — _new_id ───────────────────────────────────────────────────

def test_nfv_new_id_with_parts_deterministic():
    a = NFV._new_id("vnfInst", "vnfd-001", "site-1")
    b = NFV._new_id("vnfInst", "vnfd-001", "site-1")
    assert a == b


def test_nfv_new_id_starts_with_prefix():
    result = NFV._new_id("nsInst", "nsd-1")
    assert result.startswith("nsInst_")


def test_nfv_new_id_without_parts_unique():
    a = NFV._new_id("vnfInst")
    b = NFV._new_id("vnfInst")
    assert a != b


# ─── telecom_nfv — _join ─────────────────────────────────────────────────────

def test_nfv_join_none_returns_none():
    assert NFV._join(None) is None


def test_nfv_join_plain_string():
    assert NFV._join("tosca") == "tosca"


def test_nfv_join_list_joins():
    result = NFV._join(["tosca", "yang"])
    assert result == "tosca,yang"


def test_nfv_join_empty_list_returns_none():
    assert NFV._join([]) is None


# ─── telecom_nfv — _vid ──────────────────────────────────────────────────────

def test_nfv_vid_starts_with_at():
    result = NFV._vid("vnfInstance", "inst-001")
    assert result.startswith("at://")


def test_nfv_vid_contains_kind():
    result = NFV._vid("nsInstance", "ns-1")
    assert "nsInstance" in result


def test_nfv_vid_contains_ident():
    result = NFV._vid("vnfInstance", "inst-xyz")
    assert "inst-xyz" in result


# ─── telecom_nfv — _require ──────────────────────────────────────────────────

def test_nfv_require_present_does_not_raise():
    NFV._require({"vnfdId": "v1", "nsInstanceId": "ns1"}, ["vnfdId", "nsInstanceId"])


def test_nfv_require_missing_raises():
    with pytest.raises(ValueError):
        NFV._require({"vnfdId": "v1"}, ["vnfdId", "nsInstanceId"])


# ─── telecom_nfv — _caller ───────────────────────────────────────────────────

def test_nfv_caller_uses_caller_did():
    result = NFV._caller({"callerDid": "did:web:vnfm.etzhayyim.com"})
    assert result == "did:web:vnfm.etzhayyim.com"


def test_nfv_caller_falls_back_to_telecom_did():
    result = NFV._caller({})
    assert result == NFV.TELECOM_DID


# ─── telecom_nfv — _require_vault_ref ────────────────────────────────────────

def test_nfv_require_vault_ref_valid_passes():
    NFV._require_vault_ref("vault://nfv-key", "key")


def test_nfv_require_vault_ref_none_passes():
    NFV._require_vault_ref(None, "key")


def test_nfv_require_vault_ref_invalid_raises():
    with pytest.raises(ValueError):
        NFV._require_vault_ref("plain-text", "key")


# ─── telecom_nfv — _require_hash_prefix ──────────────────────────────────────

def test_nfv_require_hash_prefix_sha256_ok():
    NFV._require_hash_prefix("sha256:abc", "field")


def test_nfv_require_hash_prefix_invalid_raises():
    with pytest.raises(ValueError):
        NFV._require_hash_prefix("plain:bad", "field")


# ─── telecom_nfv — constants ─────────────────────────────────────────────────

def test_nfv_telecom_did_starts_with_did():
    assert NFV.TELECOM_DID.startswith("did:")


def test_nfv_descriptor_formats_is_set():
    assert isinstance(NFV.DESCRIPTOR_FORMATS, set)


def test_nfv_descriptor_formats_contains_tosca():
    assert "tosca" in NFV.DESCRIPTOR_FORMATS


def test_nfv_vnf_kinds_is_set():
    assert isinstance(NFV.VNF_KINDS, set)


def test_nfv_scale_kinds_is_set():
    assert isinstance(NFV.SCALE_KINDS, set)


def test_nfv_scale_kinds_contains_horizontal():
    assert "horizontal" in NFV.SCALE_KINDS


def test_nfv_scale_directions_is_set():
    assert isinstance(NFV.SCALE_DIRECTIONS, set)


def test_nfv_heal_causes_is_set():
    assert isinstance(NFV.HEAL_CAUSES, set)


def test_nfv_southbound_protocols_is_set():
    assert isinstance(NFV.SOUTHBOUND_PROTOCOLS, set)


def test_nfv_termination_kinds_is_set():
    assert isinstance(NFV.TERMINATION_KINDS, set)
