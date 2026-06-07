"""telecom Phase 15 primitives — TSN (IEEE 802.1 Time-Sensitive Networking).

Eight BPMN service tasks:

  - telecom.tsn.domain.register
  - telecom.tsn.bridge.register
  - telecom.tsn.gptp.provision
  - telecom.tsn.stream.reserve
  - telecom.tsn.shaper.apply
  - telecom.tsn.frer.enable
  - telecom.tsn.sync.deviation       (auto breach=true if |offset_ns| > 1000)
  - telecom.tsn.sla.breach            (auto-mints ticketId)

Discipline:
  - TAS gate schedule body persists only via vault://+sha256.
  - Source clock-id (PTPv2 EUI-64) persisted as sha256 hash.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.tsn"

PROFILE_KINDS = {"industrial_iec_iet", "automotive_802_1dg", "audio_video_802_1ba",
                 "fronthaul_802_1cm", "general_802_1as_2020"}
CONTROLLER_KINDS = {"fully_distributed", "fully_centralized_cnc", "hybrid_cuc_cnc"}
BRIDGE_KINDS = {"endpoint_talker", "endpoint_listener", "endpoint_dual",
                "transit_bridge", "edge_bridge", "tsn_du_translator", "tsn_5g_aware"}
SHAPER_KINDS = {"cbs", "tas", "ats", "strict_priority", "qci", "frame_preemption"}
GPTP_PROFILES = {"802_1as_2020", "802_1as_2011", "ptpv2_default",
                 "automotive_aerospace", "fronthaul_802_1cm"}
RESERVATION_KINDS = {"srp_legacy", "qcc_centralized", "qcc_distributed", "yang_uni"}
SHAPER_ACTIONS = {"apply", "modify", "delete"}
REPLICATION_KINDS = {"disjoint_paths", "max_disjoint", "node_disjoint",
                     "link_disjoint", "k_safe"}
DEVIATION_KINDS = {"offset_drift", "path_delay_drift", "frequency_drift",
                   "gm_loss", "bmca_change"}
BREACH_KINDS = {"latency", "jitter", "frame_loss", "gate_violation",
                "shaper_overrun", "sync_loss"}
SEVERITIES = {"minor", "major", "critical"}

# Default sync threshold: 802.1AS class A profile = ±1 µs end-to-end.
# Single-hop offset breach threshold defaults to 1000 ns.
DEFAULT_SYNC_OFFSET_BREACH_NS = 1000


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _hash_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _new_id(prefix: str, *parts: Any) -> str:
    if parts:
        digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]
        return f"{prefix}_{digest}"
    return f"{prefix}_{secrets.token_urlsafe(16).replace('-', '').replace('_', '')[:20]}"


def _join(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        items = [str(v).strip() for v in value if str(v).strip()]
        return ",".join(items) if items else None
    text = str(value).strip()
    return text or None


def _join_vids(values: Any, kind: str) -> str | None:
    if values is None or not isinstance(values, (list, tuple, set)):
        return None
    vids = [_vid(kind, str(v).strip()) for v in values if str(v).strip()]
    return ",".join(vids) if vids else None


def _require(payload: dict[str, Any], fields: list[str]) -> None:
    missing = [f for f in fields if payload.get(f) in (None, "")]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")


def _caller(payload: dict[str, Any]) -> str:
    return str(payload.get("callerDid") or TELECOM_DID)


def _audit(payload: dict[str, Any]) -> dict[str, Any]:
    did = _caller(payload)
    return {
        "created_at": _now_iso(),
        "sensitivity_ord": 2,
        "org_id": did,
        "user_id": did,
        "actor_id": ACTOR_TAG,
    }


def _insert(table: str, row: dict[str, Any], *, dry_run: bool = False) -> None:
    if dry_run:
        return
    get_kotoba_client().insert_row(table, row)


def _vid(kind: str, ident: str) -> str:
    return f"at://did:web:telecom.etzhayyim.com/com.etzhayyim.apps.telecom.{kind}/{ident}"


def _require_vault_ref(value: str | None, field: str) -> None:
    if value and not value.startswith("vault://"):
        raise ValueError(f"{field} must be a vault:// pointer")


def _require_hash_prefix(value: str, field: str) -> None:
    if not (value.startswith("sha256:") or value.startswith("sha384:") or value.startswith("sha512:")):
        raise ValueError(f"{field} must be prefixed with sha256:|sha384:|sha512:")


# ─── Task implementations ───────────────────────────────────────────────


def task_telecom_tsn_domain_register(
    ownerOrgId: str = "", displayName: str = "", profileKind: str = "",
    controllerKind: str = "", gptpDomainNumber: int = 0, observedAt: str = "",
    domainId: str = "", snpnId: str = "", controllerEndpoint: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"ownerOrgId": ownerOrgId, "displayName": displayName,
               "profileKind": profileKind, "controllerKind": controllerKind,
               "gptpDomainNumber": gptpDomainNumber,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["ownerOrgId", "displayName", "profileKind",
                       "controllerKind", "gptpDomainNumber", "observedAt"])
    if profileKind not in PROFILE_KINDS:
        raise ValueError(f"unsupported profileKind: {profileKind}")
    if controllerKind not in CONTROLLER_KINDS:
        raise ValueError(f"unsupported controllerKind: {controllerKind}")
    d_id = domainId.strip() or _new_id("tsnd", ownerOrgId, displayName, gptpDomainNumber)
    vid = _vid("tsnDomain", d_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "domain_id": d_id, "owner_org_id": ownerOrgId,
        "display_name": displayName, "profile_kind": profileKind,
        "snpn_vid": _vid("npnSnpnDeployment", snpnId) if snpnId else None,
        "controller_kind": controllerKind,
        "controller_endpoint": controllerEndpoint or None,
        "gptp_domain_number": int(gptpDomainNumber),
        "registered_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_tsn_domain", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "domainId": d_id, "status": row["status"]}


def task_telecom_tsn_bridge_register(
    domainId: str = "", vendor: str = "", model: str = "",
    bridgeKind: str = "", portCount: int = 0,
    supportedShapers: Any = None, observedAt: str = "",
    bridgeId: str = "", supportsFrer: bool | None = None,
    supportsSrp: bool | None = None, attachedAssetId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"domainId": domainId, "vendor": vendor, "model": model,
               "bridgeKind": bridgeKind, "portCount": portCount,
               "supportedShapers": supportedShapers,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["domainId", "vendor", "model", "bridgeKind",
                       "portCount", "supportedShapers", "observedAt"])
    if bridgeKind not in BRIDGE_KINDS:
        raise ValueError(f"unsupported bridgeKind: {bridgeKind}")
    if not isinstance(supportedShapers, (list, tuple)) or not supportedShapers:
        raise ValueError("supportedShapers must be a non-empty list")
    for s in supportedShapers:
        if s not in SHAPER_KINDS:
            raise ValueError(f"unsupported shaper kind: {s}")
    pc = int(portCount)
    if pc <= 0:
        raise ValueError("portCount must be > 0")
    b_id = bridgeId.strip() or _new_id("tsnb", domainId, vendor, model, observedAt)
    vid = _vid("tsnBridge", b_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "bridge_id": b_id,
        "domain_vid": _vid("tsnDomain", domainId),
        "vendor": vendor, "model": model,
        "bridge_kind": bridgeKind, "port_count": pc,
        "supported_shapers": _join(supportedShapers),
        "supports_frer": bool(supportsFrer) if supportsFrer is not None else None,
        "supports_srp": bool(supportsSrp) if supportsSrp is not None else None,
        "attached_asset_vid": _vid("networkAsset", attachedAssetId) if attachedAssetId else None,
        "registered_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_tsn_bridge", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "bridgeId": b_id, "status": row["status"]}


def task_telecom_tsn_gptp_provision(
    domainId: str = "", grandmasterBridgeId: str = "", profileKind: str = "",
    syncIntervalLog: int = 0, announceIntervalLog: int = 0, observedAt: str = "",
    syncProfileId: str = "",
    priority1: int | None = None, priority2: int | None = None,
    redundantGmBridgeIds: Any = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"domainId": domainId,
               "grandmasterBridgeId": grandmasterBridgeId,
               "profileKind": profileKind,
               "syncIntervalLog": syncIntervalLog,
               "announceIntervalLog": announceIntervalLog,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["domainId", "grandmasterBridgeId", "profileKind",
                       "observedAt"])
    if profileKind not in GPTP_PROFILES:
        raise ValueError(f"unsupported profileKind: {profileKind}")
    s_id = syncProfileId.strip() or _new_id("gptp", domainId, grandmasterBridgeId)
    vid = _vid("tsnSyncProfile", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "sync_profile_id": s_id,
        "domain_vid": _vid("tsnDomain", domainId),
        "grandmaster_bridge_vid": _vid("tsnBridge", grandmasterBridgeId),
        "profile_kind": profileKind,
        "sync_interval_log": int(syncIntervalLog),
        "announce_interval_log": int(announceIntervalLog),
        "priority1": int(priority1) if priority1 is not None else None,
        "priority2": int(priority2) if priority2 is not None else None,
        "redundant_gm_bridge_vids": _join_vids(redundantGmBridgeIds, "tsnBridge"),
        "provisioned_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_tsn_sync_profile", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "syncProfileId": s_id, "status": row["status"]}


def task_telecom_tsn_stream_reserve(
    domainId: str = "", talkerEndpointId: str = "",
    listenerEndpointIds: Any = None, trafficClass: int = 0,
    maxFrameBytes: int = 0, framesPerInterval: int = 0,
    intervalNs: int = 0, maxLatencyNs: int = 0,
    reservationKind: str = "", observedAt: str = "",
    streamId: str = "", streamRank: int | None = None,
    pathBridgeIds: Any = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"domainId": domainId, "talkerEndpointId": talkerEndpointId,
               "listenerEndpointIds": listenerEndpointIds,
               "reservationKind": reservationKind,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["domainId", "talkerEndpointId", "listenerEndpointIds",
                       "reservationKind", "observedAt"])
    if reservationKind not in RESERVATION_KINDS:
        raise ValueError(f"unsupported reservationKind: {reservationKind}")
    if not isinstance(listenerEndpointIds, (list, tuple)) or not listenerEndpointIds:
        raise ValueError("listenerEndpointIds must be a non-empty list")
    if int(maxFrameBytes) <= 0 or int(framesPerInterval) <= 0 or int(intervalNs) <= 0 or int(maxLatencyNs) <= 0:
        raise ValueError("maxFrameBytes / framesPerInterval / intervalNs / maxLatencyNs must be > 0")
    s_id = streamId.strip() or _new_id("tsns", domainId, talkerEndpointId, observedAt)
    vid = _vid("tsnStream", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "stream_id": s_id,
        "domain_vid": _vid("tsnDomain", domainId),
        "talker_endpoint_vid": _vid("tsnBridge", talkerEndpointId),
        "listener_endpoint_vids": _join_vids(listenerEndpointIds, "tsnBridge"),
        "stream_rank": int(streamRank) if streamRank is not None else None,
        "traffic_class": int(trafficClass),
        "max_frame_bytes": int(maxFrameBytes),
        "frames_per_interval": int(framesPerInterval),
        "interval_ns": int(intervalNs),
        "max_latency_ns": int(maxLatencyNs),
        "path_bridge_vids": _join_vids(pathBridgeIds, "tsnBridge"),
        "reservation_kind": reservationKind,
        "reserved_at": observedAt,
        "status": "reserved",
        **_audit(payload),
    }
    _insert("vertex_telecom_tsn_stream", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "streamId": s_id, "status": row["status"]}


def task_telecom_tsn_shaper_apply(
    bridgeId: str = "", portIndex: int = 0, shaperKind: str = "",
    trafficClass: int = 0, action: str = "", observedAt: str = "",
    shaperId: str = "", idleSlopeBps: int | None = None,
    gateScheduleHash: str = "", gateScheduleRef: str = "",
    cycleTimeNs: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"bridgeId": bridgeId, "portIndex": portIndex,
               "shaperKind": shaperKind, "trafficClass": trafficClass,
               "action": action, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["bridgeId", "shaperKind", "action", "observedAt"])
    if shaperKind not in SHAPER_KINDS:
        raise ValueError(f"unsupported shaperKind: {shaperKind}")
    if action not in SHAPER_ACTIONS:
        raise ValueError(f"unsupported action: {action}")
    if shaperKind == "cbs" and idleSlopeBps is None:
        raise ValueError("idleSlopeBps is required for cbs shaper")
    if shaperKind == "tas":
        if not gateScheduleHash:
            raise ValueError("gateScheduleHash is required for tas shaper")
        _require_hash_prefix(gateScheduleHash, "gateScheduleHash")
        _require_vault_ref(gateScheduleRef, "gateScheduleRef")
    s_id = shaperId.strip() or _new_id("shp", bridgeId, portIndex, shaperKind, observedAt)
    vid = _vid("tsnShaper", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "shaper_id": s_id,
        "bridge_vid": _vid("tsnBridge", bridgeId),
        "port_index": int(portIndex),
        "shaper_kind": shaperKind,
        "traffic_class": int(trafficClass),
        "idle_slope_bps": int(idleSlopeBps) if idleSlopeBps is not None else None,
        "gate_schedule_hash": gateScheduleHash or None,
        "gate_schedule_ref": gateScheduleRef or None,
        "cycle_time_ns": int(cycleTimeNs) if cycleTimeNs is not None else None,
        "action": action,
        "observed_at": observedAt,
        "status": "applied" if action != "delete" else "deleted",
        **_audit(payload),
    }
    _insert("vertex_telecom_tsn_shaper", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "shaperId": s_id, "status": row["status"]}


def task_telecom_tsn_frer_enable(
    streamId: str = "", replicationKind: str = "",
    replicationCount: int = 0, observedAt: str = "",
    frerProfileId: str = "",
    replicationPathBridgeIds: Any = None,
    eliminationBridgeIds: Any = None,
    sequenceRecoveryWindow: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"streamId": streamId, "replicationKind": replicationKind,
               "replicationCount": replicationCount,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["streamId", "replicationKind", "observedAt"])
    if replicationKind not in REPLICATION_KINDS:
        raise ValueError(f"unsupported replicationKind: {replicationKind}")
    rc = int(replicationCount)
    if rc < 2:
        raise ValueError("replicationCount must be >= 2")
    f_id = frerProfileId.strip() or _new_id("frer", streamId, replicationKind, observedAt)
    vid = _vid("tsnFrerProfile", f_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "frer_profile_id": f_id,
        "stream_vid": _vid("tsnStream", streamId),
        "replication_kind": replicationKind,
        "replication_count": rc,
        "replication_path_bridge_vids": _join_vids(replicationPathBridgeIds, "tsnBridge"),
        "elimination_bridge_vids": _join_vids(eliminationBridgeIds, "tsnBridge"),
        "sequence_recovery_window": int(sequenceRecoveryWindow) if sequenceRecoveryWindow is not None else None,
        "enabled_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_tsn_frer_profile", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "frerProfileId": f_id, "status": row["status"]}


def task_telecom_tsn_sync_deviation(
    syncProfileId: str = "", observedBridgeId: str = "",
    deviationKind: str = "", offsetNs: int = 0, observedAt: str = "",
    deviationId: str = "",
    pathDelayNs: int | None = None, pathDelayVarianceNs: int | None = None,
    sourceClockId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"syncProfileId": syncProfileId,
               "observedBridgeId": observedBridgeId,
               "deviationKind": deviationKind,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["syncProfileId", "observedBridgeId", "deviationKind",
                       "observedAt"])
    if deviationKind not in DEVIATION_KINDS:
        raise ValueError(f"unsupported deviationKind: {deviationKind}")
    off = int(offsetNs)
    breach = abs(off) > DEFAULT_SYNC_OFFSET_BREACH_NS or deviationKind in {"gm_loss", "bmca_change"}
    d_id = deviationId.strip() or _new_id("syndev", syncProfileId, observedBridgeId, observedAt)
    vid = _vid("tsnSyncDeviation", d_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "deviation_id": d_id,
        "sync_profile_vid": _vid("tsnSyncProfile", syncProfileId),
        "observed_bridge_vid": _vid("tsnBridge", observedBridgeId),
        "deviation_kind": deviationKind,
        "offset_ns": off,
        "path_delay_ns": int(pathDelayNs) if pathDelayNs is not None else None,
        "path_delay_variance_ns": int(pathDelayVarianceNs) if pathDelayVarianceNs is not None else None,
        "source_clock_id_hash": _hash_id(sourceClockId) if sourceClockId else None,
        "breach": breach,
        "observed_at": observedAt,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_tsn_sync_deviation", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "deviationId": d_id,
            "breach": breach, "status": row["status"]}


def task_telecom_tsn_sla_breach(
    streamId: str = "", breachKind: str = "", severity: str = "",
    witnessBridgeId: str = "", observedAt: str = "",
    breachId: str = "",
    observedLatencyNs: int | None = None, slaLatencyNs: int | None = None,
    observedJitterNs: int | None = None, observedFrameLossPpm: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"streamId": streamId, "breachKind": breachKind,
               "severity": severity, "witnessBridgeId": witnessBridgeId,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["streamId", "breachKind", "severity",
                       "witnessBridgeId", "observedAt"])
    if breachKind not in BREACH_KINDS:
        raise ValueError(f"unsupported breachKind: {breachKind}")
    if severity not in SEVERITIES:
        raise ValueError(f"unsupported severity: {severity}")
    b_id = breachId.strip() or _new_id("tsnbrc", streamId, breachKind, observedAt)
    t_id = _new_id("tkt", b_id)
    vid = _vid("tsnSlaBreach", b_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "breach_id": b_id,
        "stream_vid": _vid("tsnStream", streamId),
        "breach_kind": breachKind,
        "severity": severity,
        "observed_latency_ns": int(observedLatencyNs) if observedLatencyNs is not None else None,
        "sla_latency_ns": int(slaLatencyNs) if slaLatencyNs is not None else None,
        "observed_jitter_ns": int(observedJitterNs) if observedJitterNs is not None else None,
        "observed_frame_loss_ppm": int(observedFrameLossPpm) if observedFrameLossPpm is not None else None,
        "witness_bridge_vid": _vid("tsnBridge", witnessBridgeId),
        "ticket_id": t_id,
        "observed_at": observedAt,
        "status": "open",
        **_audit(payload),
    }
    _insert("vertex_telecom_tsn_sla_breach", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "breachId": b_id,
            "ticketId": t_id, "status": row["status"]}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.tsn.domain.register", single_value=False, timeout_ms=timeout_ms)(task_telecom_tsn_domain_register)
    worker.task(task_type="telecom.tsn.bridge.register", single_value=False, timeout_ms=timeout_ms)(task_telecom_tsn_bridge_register)
    worker.task(task_type="telecom.tsn.gptp.provision",  single_value=False, timeout_ms=timeout_ms)(task_telecom_tsn_gptp_provision)
    worker.task(task_type="telecom.tsn.stream.reserve",  single_value=False, timeout_ms=timeout_ms)(task_telecom_tsn_stream_reserve)
    worker.task(task_type="telecom.tsn.shaper.apply",    single_value=False, timeout_ms=timeout_ms)(task_telecom_tsn_shaper_apply)
    worker.task(task_type="telecom.tsn.frer.enable",     single_value=False, timeout_ms=timeout_ms)(task_telecom_tsn_frer_enable)
    worker.task(task_type="telecom.tsn.sync.deviation",  single_value=False, timeout_ms=timeout_ms)(task_telecom_tsn_sync_deviation)
    worker.task(task_type="telecom.tsn.sla.breach",      single_value=False, timeout_ms=timeout_ms)(task_telecom_tsn_sla_breach)

    worker.task(task_type="telecom.tsn.sync.deviation",  single_value=False, timeout_ms=timeout_ms)(task_telecom_tsn_sync_deviation)
    worker.task(task_type="telecom.tsn.sla.breach",      single_value=False, timeout_ms=timeout_ms)(task_telecom_tsn_sla_breach)
