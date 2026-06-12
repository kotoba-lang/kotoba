"""telecom Phase 16 primitives — TIP Phoenix Open Optical (TIP MUST).

Eight BPMN service tasks:

  - telecom.opt.domain.register
  - telecom.opt.ols.register
  - telecom.opt.roadm.register
  - telecom.opt.fiber.register
  - telecom.opt.dwdm.provision
  - telecom.opt.otn.provision
  - telecom.opt.alarm.record       (auto-mints ticketId)
  - telecom.opt.pm.record          (auto breach when |value| crosses slaThreshold)

Discipline:
  - No PII / customer identifiers; physical-layer optical data only.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.optical"

CONTROLLER_KINDS = {"transport_pce", "goldstone", "gnpy_planner", "ietf_actn", "vendor_proprietary"}
SOUTHBOUND_PROTOCOLS = {"netconf_openconfig", "netconf_openroadm", "tapi", "openroadm_yang", "vendor_cli"}
MODULATIONS = {"bpsk", "qpsk", "8qam", "16qam", "32qam", "64qam", "pcs_64qam"}
ROADM_KINDS = {"cdc_f", "cd_f", "directionless", "colorless_only", "fixed_oadm"}
FIBER_TYPES = {"smf28", "nzdsf", "lefiber", "tw_reach", "g653", "g655", "g657"}
AMPLIFIER_KINDS = {"edfa_inline", "edfa_booster", "edfa_preamp", "raman", "hybrid_raman_edfa", "none"}
FEC_KINDS = {"sd_fec_15", "sd_fec_25", "sd_fec_28", "hard_decision_g709", "openroadm_25"}
TRANSPARENT_TO = {"otn", "ethernet_lan_phy", "fc"}
ODU_KINDS = {"odu0", "odu1", "odu2", "odu2e", "odu3", "odu4", "oduflex", "ofec_otu4", "otuc1", "otuc2", "otuc4"}
CLIENT_SERVICE_KINDS = {"ranxhaul", "service", "pdu_session", "ntn_feeder", "interconnect", "wholesale_l1"}
PROTECTION_KINDS = {"unprotected", "1plus1", "1plus1_optical", "snc_p", "subnetwork_connection_protection", "shared_mesh"}
ALARM_SOURCE_KINDS = {"roadm", "fiber_span", "dwdm_channel", "otn_connection", "ols", "amplifier", "transponder"}
ALARM_KINDS = {"los", "lof", "los_p", "bdi", "tim", "deg", "ber_excessive", "osnr_min",
               "rx_power_low", "tx_power_high", "amplifier_gain_drift", "wavelength_drift"}
SEVERITIES = {"warning", "minor", "major", "critical"}
PM_SOURCE_KINDS = {"roadm", "fiber_span", "dwdm_channel", "otn_connection", "amplifier", "transponder"}
PM_METRICS = {"rx_power_dbm", "tx_power_dbm", "osnr_db", "pre_fec_ber", "post_fec_ber",
              "q_factor_db", "chromatic_dispersion_ps_nm", "pmd_ps", "amplifier_gain_db"}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


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


# ─── Task implementations ───────────────────────────────────────────────


def task_telecom_opt_domain_register(
    ownerOrgId: str = "", displayName: str = "", controllerKind: str = "",
    jurisdiction: str = "", observedAt: str = "",
    domainId: str = "", controllerEndpoint: str = "",
    southboundProtocols: Any = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"ownerOrgId": ownerOrgId, "displayName": displayName,
               "controllerKind": controllerKind, "jurisdiction": jurisdiction,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["ownerOrgId", "displayName", "controllerKind",
                       "jurisdiction", "observedAt"])
    if controllerKind not in CONTROLLER_KINDS:
        raise ValueError(f"unsupported controllerKind: {controllerKind}")
    if southboundProtocols and isinstance(southboundProtocols, (list, tuple)):
        for p in southboundProtocols:
            if p not in SOUTHBOUND_PROTOCOLS:
                raise ValueError(f"unsupported southbound protocol: {p}")
    d_id = domainId.strip() or _new_id("optd", ownerOrgId, displayName, jurisdiction)
    vid = _vid("opticalDomain", d_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "domain_id": d_id, "owner_org_id": ownerOrgId,
        "display_name": displayName,
        "controller_kind": controllerKind,
        "controller_endpoint": controllerEndpoint or None,
        "southbound_protocols": _join(southboundProtocols),
        "jurisdiction": jurisdiction,
        "registered_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_optical_domain", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "domainId": d_id, "status": row["status"]}


def task_telecom_opt_ols_register(
    domainId: str = "", vendor: str = "", model: str = "",
    mustSpecVersion: str = "", totalSpectrumGhz: float = 0.0,
    channelGridGhz: float = 0.0, supportedModulations: Any = None,
    observedAt: str = "",
    olsId: str = "", transponderProfile: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"domainId": domainId, "vendor": vendor, "model": model,
               "mustSpecVersion": mustSpecVersion,
               "supportedModulations": supportedModulations,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["domainId", "vendor", "model", "mustSpecVersion",
                       "supportedModulations", "observedAt"])
    if not isinstance(supportedModulations, (list, tuple)) or not supportedModulations:
        raise ValueError("supportedModulations must be a non-empty list")
    for m in supportedModulations:
        if m not in MODULATIONS:
            raise ValueError(f"unsupported modulation: {m}")
    ts = float(totalSpectrumGhz)
    cg = float(channelGridGhz)
    if ts <= 0 or cg <= 0:
        raise ValueError("totalSpectrumGhz / channelGridGhz must be > 0")
    o_id = olsId.strip() or _new_id("ols", domainId, vendor, model, mustSpecVersion)
    vid = _vid("opticalOls", o_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "ols_id": o_id,
        "domain_vid": _vid("opticalDomain", domainId),
        "vendor": vendor, "model": model,
        "must_spec_version": mustSpecVersion,
        "transponder_profile": transponderProfile or None,
        "total_spectrum_ghz": ts,
        "channel_grid_ghz": cg,
        "supported_modulations": _join(supportedModulations),
        "registered_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_optical_ols", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "olsId": o_id, "status": row["status"]}


def task_telecom_opt_roadm_register(
    olsId: str = "", displayName: str = "", roadmKind: str = "",
    degreeCount: int = 0, addDropPortCount: int = 0, wssVendor: str = "",
    observedAt: str = "",
    roadmId: str = "", siteId: str = "", attachedAssetId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"olsId": olsId, "displayName": displayName,
               "roadmKind": roadmKind, "wssVendor": wssVendor,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["olsId", "displayName", "roadmKind", "wssVendor", "observedAt"])
    if roadmKind not in ROADM_KINDS:
        raise ValueError(f"unsupported roadmKind: {roadmKind}")
    dc = int(degreeCount)
    ap = int(addDropPortCount)
    if dc <= 0 or ap < 0:
        raise ValueError("degreeCount must be > 0; addDropPortCount must be >= 0")
    r_id = roadmId.strip() or _new_id("roadm", olsId, displayName)
    vid = _vid("opticalRoadm", r_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "roadm_id": r_id,
        "ols_vid": _vid("opticalOls", olsId),
        "display_name": displayName,
        "site_vid": _vid("cellSite", siteId) if siteId else None,
        "roadm_kind": roadmKind,
        "degree_count": dc,
        "add_drop_port_count": ap,
        "wss_vendor": wssVendor,
        "attached_asset_vid": _vid("networkAsset", attachedAssetId) if attachedAssetId else None,
        "registered_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_optical_roadm", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "roadmId": r_id, "status": row["status"]}


def task_telecom_opt_fiber_register(
    olsId: str = "", sourceRoadmId: str = "", targetRoadmId: str = "",
    fiberType: str = "", lengthKm: float = 0.0, attenuationDb: float = 0.0,
    ownerOrgId: str = "", observedAt: str = "",
    spanId: str = "", dispersionPsNmKm: float | None = None,
    amplifierKind: str = "", amplifierGainDb: float | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"olsId": olsId, "sourceRoadmId": sourceRoadmId,
               "targetRoadmId": targetRoadmId, "fiberType": fiberType,
               "ownerOrgId": ownerOrgId, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["olsId", "sourceRoadmId", "targetRoadmId",
                       "fiberType", "ownerOrgId", "observedAt"])
    if fiberType not in FIBER_TYPES:
        raise ValueError(f"unsupported fiberType: {fiberType}")
    if amplifierKind and amplifierKind not in AMPLIFIER_KINDS:
        raise ValueError(f"unsupported amplifierKind: {amplifierKind}")
    lk = float(lengthKm)
    att = float(attenuationDb)
    if lk <= 0 or att < 0:
        raise ValueError("lengthKm must be > 0; attenuationDb must be >= 0")
    s_id = spanId.strip() or _new_id("span", olsId, sourceRoadmId, targetRoadmId)
    vid = _vid("opticalFiberSpan", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "span_id": s_id,
        "ols_vid": _vid("opticalOls", olsId),
        "source_roadm_vid": _vid("opticalRoadm", sourceRoadmId),
        "target_roadm_vid": _vid("opticalRoadm", targetRoadmId),
        "fiber_type": fiberType,
        "length_km": lk,
        "attenuation_db": att,
        "dispersion_ps_nm_km": float(dispersionPsNmKm) if dispersionPsNmKm is not None else None,
        "amplifier_kind": amplifierKind or None,
        "amplifier_gain_db": float(amplifierGainDb) if amplifierGainDb is not None else None,
        "owner_org_id": ownerOrgId,
        "registered_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_optical_fiber_span", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "spanId": s_id, "status": row["status"]}


def task_telecom_opt_dwdm_provision(
    olsId: str = "", sourceRoadmId: str = "", targetRoadmId: str = "",
    centerFrequencyGhz: float = 0.0, bandwidthGhz: float = 0.0,
    modulation: str = "", lineRateGbps: float = 0.0, observedAt: str = "",
    channelId: str = "", pathSpanIds: Any = None,
    fec: str = "", oTransparentTo: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"olsId": olsId, "sourceRoadmId": sourceRoadmId,
               "targetRoadmId": targetRoadmId,
               "modulation": modulation, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["olsId", "sourceRoadmId", "targetRoadmId",
                       "modulation", "observedAt"])
    if modulation not in MODULATIONS:
        raise ValueError(f"unsupported modulation: {modulation}")
    if fec and fec not in FEC_KINDS:
        raise ValueError(f"unsupported fec: {fec}")
    if oTransparentTo and oTransparentTo not in TRANSPARENT_TO:
        raise ValueError(f"unsupported oTransparentTo: {oTransparentTo}")
    cf = float(centerFrequencyGhz)
    bw = float(bandwidthGhz)
    lr = float(lineRateGbps)
    if cf <= 0 or bw <= 0 or lr <= 0:
        raise ValueError("centerFrequencyGhz / bandwidthGhz / lineRateGbps must be > 0")
    c_id = channelId.strip() or _new_id("dwdm", olsId, sourceRoadmId, targetRoadmId, cf)
    vid = _vid("opticalDwdmChannel", c_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "channel_id": c_id,
        "ols_vid": _vid("opticalOls", olsId),
        "source_roadm_vid": _vid("opticalRoadm", sourceRoadmId),
        "target_roadm_vid": _vid("opticalRoadm", targetRoadmId),
        "path_span_vids": _join_vids(pathSpanIds, "opticalFiberSpan"),
        "center_frequency_ghz": cf,
        "bandwidth_ghz": bw,
        "modulation": modulation,
        "line_rate_gbps": lr,
        "fec": fec or None,
        "o_transparent_to": oTransparentTo or None,
        "provisioned_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_optical_dwdm_channel", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "channelId": c_id, "status": row["status"]}


def task_telecom_opt_otn_provision(
    channelId: str = "", oduKind: str = "", oduRate: str = "",
    sourceRoadmId: str = "", targetRoadmId: str = "",
    clientServiceKind: str = "", observedAt: str = "",
    otnId: str = "", clientServiceVid: str = "",
    protectionKind: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"channelId": channelId, "oduKind": oduKind, "oduRate": oduRate,
               "sourceRoadmId": sourceRoadmId, "targetRoadmId": targetRoadmId,
               "clientServiceKind": clientServiceKind,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["channelId", "oduKind", "oduRate", "sourceRoadmId",
                       "targetRoadmId", "clientServiceKind", "observedAt"])
    if oduKind not in ODU_KINDS:
        raise ValueError(f"unsupported oduKind: {oduKind}")
    if clientServiceKind not in CLIENT_SERVICE_KINDS:
        raise ValueError(f"unsupported clientServiceKind: {clientServiceKind}")
    if protectionKind and protectionKind not in PROTECTION_KINDS:
        raise ValueError(f"unsupported protectionKind: {protectionKind}")
    o_id = otnId.strip() or _new_id("otn", channelId, oduKind, sourceRoadmId, targetRoadmId)
    vid = _vid("opticalOtnConnection", o_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "otn_id": o_id,
        "channel_vid": _vid("opticalDwdmChannel", channelId),
        "odu_kind": oduKind,
        "odu_rate": oduRate,
        "source_roadm_vid": _vid("opticalRoadm", sourceRoadmId),
        "target_roadm_vid": _vid("opticalRoadm", targetRoadmId),
        "client_service_kind": clientServiceKind,
        "client_service_vid": clientServiceVid or None,
        "protection_kind": protectionKind or None,
        "provisioned_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_optical_otn_connection", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "otnId": o_id, "status": row["status"]}


def task_telecom_opt_alarm_record(
    sourceKind: str = "", sourceVid: str = "", alarmKind: str = "",
    severity: str = "", observedAt: str = "",
    alarmId: str = "", observedValue: float | None = None,
    observedUnit: str = "", ticketId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"sourceKind": sourceKind, "sourceVid": sourceVid,
               "alarmKind": alarmKind, "severity": severity,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["sourceKind", "sourceVid", "alarmKind", "severity", "observedAt"])
    if sourceKind not in ALARM_SOURCE_KINDS:
        raise ValueError(f"unsupported sourceKind: {sourceKind}")
    if alarmKind not in ALARM_KINDS:
        raise ValueError(f"unsupported alarmKind: {alarmKind}")
    if severity not in SEVERITIES:
        raise ValueError(f"unsupported severity: {severity}")
    a_id = alarmId.strip() or _new_id("oalm", sourceKind, sourceVid, alarmKind, observedAt)
    t_id = ticketId.strip() or _new_id("tkt", a_id)
    vid = _vid("opticalAlarm", a_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "alarm_id": a_id,
        "source_kind": sourceKind,
        "source_vid": sourceVid,
        "alarm_kind": alarmKind,
        "severity": severity,
        "observed_value": float(observedValue) if observedValue is not None else None,
        "observed_unit": observedUnit or None,
        "ticket_id": t_id,
        "observed_at": observedAt,
        "status": "open",
        **_audit(payload),
    }
    _insert("vertex_telecom_optical_alarm", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "alarmId": a_id,
            "ticketId": t_id, "status": row["status"]}


def task_telecom_opt_pm_record(
    sourceKind: str = "", sourceVid: str = "", metric: str = "",
    value: float = 0.0, unit: str = "", observedAt: str = "",
    pmId: str = "", binIntervalSeconds: int | None = None,
    slaThreshold: float | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"sourceKind": sourceKind, "sourceVid": sourceVid,
               "metric": metric, "unit": unit,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["sourceKind", "sourceVid", "metric", "unit", "observedAt"])
    if sourceKind not in PM_SOURCE_KINDS:
        raise ValueError(f"unsupported sourceKind: {sourceKind}")
    if metric not in PM_METRICS:
        raise ValueError(f"unsupported metric: {metric}")
    val = float(value)
    threshold = float(slaThreshold) if slaThreshold is not None else None
    breach = bool(threshold is not None and abs(val) > abs(threshold))
    p_id = pmId.strip() or _new_id("opm", sourceVid, metric, observedAt)
    vid = _vid("opticalPmEvent", p_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "pm_id": p_id,
        "source_kind": sourceKind,
        "source_vid": sourceVid,
        "metric": metric,
        "value": val,
        "unit": unit,
        "bin_interval_seconds": int(binIntervalSeconds) if binIntervalSeconds is not None else None,
        "sla_threshold": threshold,
        "breach": breach,
        "observed_at": observedAt,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_optical_pm_event", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "pmId": p_id,
            "breach": breach, "status": row["status"]}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.opt.domain.register", single_value=False, timeout_ms=timeout_ms)(task_telecom_opt_domain_register)
    worker.task(task_type="telecom.opt.ols.register",    single_value=False, timeout_ms=timeout_ms)(task_telecom_opt_ols_register)
    worker.task(task_type="telecom.opt.roadm.register",  single_value=False, timeout_ms=timeout_ms)(task_telecom_opt_roadm_register)
    worker.task(task_type="telecom.opt.fiber.register",  single_value=False, timeout_ms=timeout_ms)(task_telecom_opt_fiber_register)
    worker.task(task_type="telecom.opt.dwdm.provision",  single_value=False, timeout_ms=timeout_ms)(task_telecom_opt_dwdm_provision)
    worker.task(task_type="telecom.opt.otn.provision",   single_value=False, timeout_ms=timeout_ms)(task_telecom_opt_otn_provision)
    worker.task(task_type="telecom.opt.alarm.record",    single_value=False, timeout_ms=timeout_ms)(task_telecom_opt_alarm_record)
    worker.task(task_type="telecom.opt.pm.record",       single_value=False, timeout_ms=timeout_ms)(task_telecom_opt_pm_record)
