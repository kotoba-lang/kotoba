"""telecom Phase 14 primitives — Satellite NTN (3GPP TS 23.501 §5.4.11 / TS 38.821).

Eight BPMN service tasks:

  - telecom.ntn.satellite.register
  - telecom.ntn.earthStation.register
  - telecom.ntn.cell.provision
  - telecom.ntn.ephemeris.record
  - telecom.ntn.handover.record
  - telecom.ntn.isl.provision
  - telecom.ntn.contact.record
  - telecom.ntn.partner.register

Discipline:
  - Ephemeris payload (TLE/OMM/SP3/OEM/3GPP-NTN) persists via vault://+sha256.
  - ISL encryption keys persist via vault:// pointer.
  - `recordEarthStationContact` computes duration_seconds = los_at - aos_at.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.ntn"

ORBIT_CLASSES = {"leo", "meo", "geo", "heo", "molniya"}
SERVICE_MODES = {"transparent", "regenerative", "iot_ntn", "broadband_ntn", "messaging_only"}
STATION_KINDS = {"gateway", "tt_and_c", "feeder_link", "user_terminal_anchor", "ground_segment_as_a_service"}
GATEWAY_KINDS = {"ip_gateway", "n3iwf", "tngf", "trusted_wlan", "private_apn", "iot_ntn_gateway"}
CELL_PATTERNS = {"moving", "earth_fixed", "quasi_earth_fixed"}
PAYLOAD_KINDS = {"transparent", "regenerative_gnb", "regenerative_ng_ran", "regenerative_full"}
EPH_SOURCE_KINDS = {"operator", "celestrak", "spacetrack", "leolabs", "norad", "internal"}
EPH_FORMATS = {"tle", "omm_xml", "omm_kvn", "sp3", "ccsds_oem", "3gpp_ntn"}
HANDOVER_KINDS = {"intra_satellite", "inter_satellite", "ntn_to_tn", "tn_to_ntn", "constellation_handoff"}
HANDOVER_TRIGGERS = {"beam_sweep", "elevation_min", "load_balance", "cell_pattern_change",
                     "terrestrial_coverage", "operator_request"}
ISL_KINDS = {"optical_lct", "rf_ka", "rf_v_band", "rf_w_band", "rf_q_band"}
CONTACT_KINDS = {"feeder_uplink", "feeder_downlink", "feeder_bidirectional", "tt_and_c", "ranging"}
CONSTELLATION_KINDS = {"leo_broadband", "leo_iot", "meo_broadband", "geo_broadband",
                       "geo_messaging", "hybrid_constellation"}
SETTLEMENT_MODES = {"per_byte", "per_minute", "flat_fee", "revenue_share", "settlement_free"}


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


def _require_vault_ref(value: str | None, field: str) -> None:
    if value and not value.startswith("vault://"):
        raise ValueError(f"{field} must be a vault:// pointer")


def _require_hash_prefix(value: str, field: str) -> None:
    if not (value.startswith("sha256:") or value.startswith("sha384:") or value.startswith("sha512:")):
        raise ValueError(f"{field} must be prefixed with sha256:|sha384:|sha512:")


# ─── Task implementations ───────────────────────────────────────────────


def task_telecom_ntn_satellite_register(
    operatorOrgId: str = "", displayName: str = "", orbitClass: str = "",
    frequencyBands: Any = None, serviceModes: Any = None,
    launchedAt: str = "", observedAt: str = "",
    satelliteId: str = "", noradId: str = "", intlDesignator: str = "", eolAt: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"operatorOrgId": operatorOrgId, "displayName": displayName,
               "orbitClass": orbitClass, "frequencyBands": frequencyBands,
               "serviceModes": serviceModes, "launchedAt": launchedAt,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["operatorOrgId", "displayName", "orbitClass",
                       "frequencyBands", "serviceModes", "launchedAt", "observedAt"])
    if orbitClass not in ORBIT_CLASSES:
        raise ValueError(f"unsupported orbitClass: {orbitClass}")
    if not isinstance(frequencyBands, (list, tuple)) or not frequencyBands:
        raise ValueError("frequencyBands must be a non-empty list")
    if not isinstance(serviceModes, (list, tuple)) or not serviceModes:
        raise ValueError("serviceModes must be a non-empty list")
    for sm in serviceModes:
        if sm not in SERVICE_MODES:
            raise ValueError(f"unsupported serviceMode: {sm}")
    s_id = satelliteId.strip() or _new_id("sat", operatorOrgId, displayName, noradId or launchedAt)
    vid = _vid("ntnSatellite", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "satellite_id": s_id,
        "operator_org_id": operatorOrgId,
        "display_name": displayName,
        "orbit_class": orbitClass,
        "norad_id": noradId or None,
        "intl_designator": intlDesignator or None,
        "frequency_bands": _join(frequencyBands),
        "service_modes": _join(serviceModes),
        "launched_at": launchedAt,
        "eol_at": eolAt or None,
        "registered_at": observedAt,
        "status": "operational",
        **_audit(payload),
    }
    _insert("vertex_telecom_ntn_satellite", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "satelliteId": s_id, "status": row["status"]}


def task_telecom_ntn_earth_station_register(
    operatorOrgId: str = "", displayName: str = "", stationKind: str = "",
    latitude: float = 0.0, longitude: float = 0.0,
    jurisdiction: str = "", gatewayKind: str = "", observedAt: str = "",
    stationId: str = "", altitudeMeters: float | None = None,
    antennaCount: int | None = None, peeringNfId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"operatorOrgId": operatorOrgId, "displayName": displayName,
               "stationKind": stationKind, "jurisdiction": jurisdiction,
               "gatewayKind": gatewayKind, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["operatorOrgId", "displayName", "stationKind",
                       "jurisdiction", "gatewayKind", "observedAt"])
    if stationKind not in STATION_KINDS:
        raise ValueError(f"unsupported stationKind: {stationKind}")
    if gatewayKind not in GATEWAY_KINDS:
        raise ValueError(f"unsupported gatewayKind: {gatewayKind}")
    s_id = stationId.strip() or _new_id("es", operatorOrgId, displayName, jurisdiction)
    vid = _vid("ntnEarthStation", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "station_id": s_id,
        "operator_org_id": operatorOrgId,
        "display_name": displayName,
        "station_kind": stationKind,
        "latitude": float(latitude),
        "longitude": float(longitude),
        "altitude_meters": float(altitudeMeters) if altitudeMeters is not None else None,
        "jurisdiction": jurisdiction,
        "antenna_count": int(antennaCount) if antennaCount is not None else None,
        "gateway_kind": gatewayKind,
        "peering_nf_vid": _vid("nfInstance", peeringNfId) if peeringNfId else None,
        "registered_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_ntn_earth_station", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "stationId": s_id, "status": row["status"]}


def task_telecom_ntn_cell_provision(
    satelliteId: str = "", ranNodeId: str = "", cellPattern: str = "",
    beamCount: int = 0, plmnId: str = "", frequencyBand: str = "",
    payloadKind: str = "", validFrom: str = "", observedAt: str = "",
    ntnCellId: str = "", snssai: str = "",
    jurisdiction: str = "", validUntil: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"satelliteId": satelliteId, "ranNodeId": ranNodeId,
               "cellPattern": cellPattern, "plmnId": plmnId,
               "frequencyBand": frequencyBand, "payloadKind": payloadKind,
               "validFrom": validFrom, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["satelliteId", "ranNodeId", "cellPattern", "plmnId",
                       "frequencyBand", "payloadKind", "validFrom", "observedAt"])
    if cellPattern not in CELL_PATTERNS:
        raise ValueError(f"unsupported cellPattern: {cellPattern}")
    if payloadKind not in PAYLOAD_KINDS:
        raise ValueError(f"unsupported payloadKind: {payloadKind}")
    bc = int(beamCount)
    if bc <= 0:
        raise ValueError("beamCount must be > 0")
    c_id = ntnCellId.strip() or _new_id("ntnc", satelliteId, ranNodeId, frequencyBand)
    vid = _vid("ntnCell", c_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "ntn_cell_id": c_id,
        "satellite_vid": _vid("ntnSatellite", satelliteId),
        "ran_node_vid": _vid("ranNode", ranNodeId),
        "cell_pattern": cellPattern,
        "beam_count": bc,
        "plmn_id": plmnId,
        "snssai": snssai or None,
        "frequency_band": frequencyBand,
        "payload_kind": payloadKind,
        "jurisdiction": jurisdiction or None,
        "valid_from": validFrom,
        "valid_until": validUntil or None,
        "provisioned_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_ntn_cell", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "ntnCellId": c_id, "status": row["status"]}


def task_telecom_ntn_ephemeris_record(
    satelliteId: str = "", sourceKind: str = "", epochAt: str = "",
    payloadFormat: str = "", payloadHash: str = "", observedAt: str = "",
    ephemerisId: str = "", sourceProvider: str = "",
    payloadRef: str = "", payloadSize: int | None = None, validUntil: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"satelliteId": satelliteId, "sourceKind": sourceKind,
               "epochAt": epochAt, "payloadFormat": payloadFormat,
               "payloadHash": payloadHash, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["satelliteId", "sourceKind", "epochAt",
                       "payloadFormat", "payloadHash", "observedAt"])
    if sourceKind not in EPH_SOURCE_KINDS:
        raise ValueError(f"unsupported sourceKind: {sourceKind}")
    if payloadFormat not in EPH_FORMATS:
        raise ValueError(f"unsupported payloadFormat: {payloadFormat}")
    _require_hash_prefix(payloadHash, "payloadHash")
    _require_vault_ref(payloadRef, "payloadRef")
    e_id = ephemerisId.strip() or _new_id("eph", satelliteId, payloadFormat, epochAt)
    vid = _vid("ntnEphemeris", e_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "ephemeris_id": e_id,
        "satellite_vid": _vid("ntnSatellite", satelliteId),
        "source_kind": sourceKind,
        "source_provider": sourceProvider or None,
        "epoch_at": epochAt,
        "payload_format": payloadFormat,
        "payload_hash": payloadHash,
        "payload_ref": payloadRef or None,
        "payload_size": int(payloadSize) if payloadSize is not None else None,
        "valid_until": validUntil or None,
        "observed_at": observedAt,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_ntn_ephemeris", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "ephemerisId": e_id, "status": row["status"]}


def task_telecom_ntn_handover_record(
    profileId: str = "", handoverKind: str = "",
    sourceCellId: str = "", targetCellId: str = "",
    triggerKind: str = "", observedAt: str = "",
    handoverId: str = "",
    sourceSatelliteId: str = "", targetSatelliteId: str = "",
    dopplerOffsetHz: float | None = None, oneWayDelayMs: float | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"profileId": profileId, "handoverKind": handoverKind,
               "sourceCellId": sourceCellId, "targetCellId": targetCellId,
               "triggerKind": triggerKind, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["profileId", "handoverKind", "sourceCellId",
                       "targetCellId", "triggerKind", "observedAt"])
    if handoverKind not in HANDOVER_KINDS:
        raise ValueError(f"unsupported handoverKind: {handoverKind}")
    if triggerKind not in HANDOVER_TRIGGERS:
        raise ValueError(f"unsupported triggerKind: {triggerKind}")
    h_id = handoverId.strip() or _new_id("ntnho", profileId, sourceCellId, targetCellId, observedAt)
    vid = _vid("ntnHandover", h_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "handover_id": h_id,
        "profile_vid": _vid("subscriberProfile5g", profileId),
        "handover_kind": handoverKind,
        "source_cell_vid": _vid("ntnCell", sourceCellId),
        "target_cell_vid": _vid("ntnCell", targetCellId),
        "source_satellite_vid": _vid("ntnSatellite", sourceSatelliteId) if sourceSatelliteId else None,
        "target_satellite_vid": _vid("ntnSatellite", targetSatelliteId) if targetSatelliteId else None,
        "trigger_kind": triggerKind,
        "doppler_offset_hz": float(dopplerOffsetHz) if dopplerOffsetHz is not None else None,
        "one_way_delay_ms": float(oneWayDelayMs) if oneWayDelayMs is not None else None,
        "observed_at": observedAt,
        "status": "completed",
        **_audit(payload),
    }
    _insert("vertex_telecom_ntn_handover", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "handoverId": h_id, "status": row["status"]}


def task_telecom_ntn_isl_provision(
    sourceSatelliteId: str = "", targetSatelliteId: str = "",
    linkKind: str = "", capacityMbps: float = 0.0,
    validFrom: str = "", observedAt: str = "",
    islId: str = "", frequencyBand: str = "", encryptionRef: str = "",
    validUntil: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"sourceSatelliteId": sourceSatelliteId,
               "targetSatelliteId": targetSatelliteId,
               "linkKind": linkKind, "validFrom": validFrom,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["sourceSatelliteId", "targetSatelliteId",
                       "linkKind", "validFrom", "observedAt"])
    if linkKind not in ISL_KINDS:
        raise ValueError(f"unsupported linkKind: {linkKind}")
    cap = float(capacityMbps)
    if cap <= 0:
        raise ValueError("capacityMbps must be > 0")
    _require_vault_ref(encryptionRef, "encryptionRef")
    i_id = islId.strip() or _new_id("isl", sourceSatelliteId, targetSatelliteId, linkKind)
    vid = _vid("ntnIsl", i_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "isl_id": i_id,
        "source_satellite_vid": _vid("ntnSatellite", sourceSatelliteId),
        "target_satellite_vid": _vid("ntnSatellite", targetSatelliteId),
        "link_kind": linkKind,
        "capacity_mbps": cap,
        "frequency_band": frequencyBand or None,
        "encryption_ref": encryptionRef or None,
        "valid_from": validFrom,
        "valid_until": validUntil or None,
        "provisioned_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_ntn_isl", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "islId": i_id, "status": row["status"]}


def task_telecom_ntn_contact_record(
    stationId: str = "", satelliteId: str = "", contactKind: str = "",
    aosAt: str = "", losAt: str = "", observedAt: str = "",
    contactId: str = "",
    peakElevationDeg: float | None = None, dopplerShiftHz: float | None = None,
    ingressBytes: int | None = None, egressBytes: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"stationId": stationId, "satelliteId": satelliteId,
               "contactKind": contactKind, "aosAt": aosAt, "losAt": losAt,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["stationId", "satelliteId", "contactKind",
                       "aosAt", "losAt", "observedAt"])
    if contactKind not in CONTACT_KINDS:
        raise ValueError(f"unsupported contactKind: {contactKind}")
    c_id = contactId.strip() or _new_id("esc", stationId, satelliteId, aosAt)
    vid = _vid("ntnContact", c_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "contact_id": c_id,
        "station_vid": _vid("ntnEarthStation", stationId),
        "satellite_vid": _vid("ntnSatellite", satelliteId),
        "contact_kind": contactKind,
        "aos_at": aosAt,
        "los_at": losAt,
        "duration_seconds": None,
        "peak_elevation_deg": float(peakElevationDeg) if peakElevationDeg is not None else None,
        "doppler_shift_hz": float(dopplerShiftHz) if dopplerShiftHz is not None else None,
        "ingress_bytes": int(ingressBytes) if ingressBytes is not None else None,
        "egress_bytes": int(egressBytes) if egressBytes is not None else None,
        "observed_at": observedAt,
        "status": "completed",
        **_audit(payload),
    }
    _insert("vertex_telecom_ntn_contact", row, dry_run=dryRun)
    duration = None
    if not dryRun:
        # Calculate duration_seconds in Python as per the original SQL logic.
        # R0: Replaced SQL calculation of duration_seconds with Python equivalent.
        aos_dt = datetime.fromisoformat(aosAt)
        los_dt = datetime.fromisoformat(losAt)
        duration_delta = los_dt - aos_dt
        duration = duration_delta.total_seconds()
        # Update the row with the calculated duration
        update_dict = {"vertex_id": vid, "duration_seconds": duration}
        get_kotoba_client().insert_row("vertex_telecom_ntn_contact", update_dict)

    return {"ok": True, "vertexId": vid, "contactId": c_id,
            "durationSeconds": duration, "status": row["status"]}


def task_telecom_ntn_partner_register(
    operatorOrgId: str = "", agreementId: str = "",
    constellationKind: str = "", plmnId: str = "",
    settlementMode: str = "", validUntil: str = "", observedAt: str = "",
    ntnPartnerId: str = "",
    supportedSatelliteIds: Any = None,
    supportedEarthStationIds: Any = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"operatorOrgId": operatorOrgId, "agreementId": agreementId,
               "constellationKind": constellationKind, "plmnId": plmnId,
               "settlementMode": settlementMode, "validUntil": validUntil,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["operatorOrgId", "agreementId", "constellationKind",
                       "plmnId", "settlementMode", "validUntil", "observedAt"])
    if constellationKind not in CONSTELLATION_KINDS:
        raise ValueError(f"unsupported constellationKind: {constellationKind}")
    if settlementMode not in SETTLEMENT_MODES:
        raise ValueError(f"unsupported settlementMode: {settlementMode}")
    p_id = ntnPartnerId.strip() or _new_id("ntnpart", operatorOrgId, plmnId, constellationKind)
    vid = _vid("ntnPartner", p_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "ntn_partner_id": p_id,
        "operator_org_id": operatorOrgId,
        "agreement_vid": _vid("interconnectAgreement", agreementId),
        "constellation_kind": constellationKind,
        "supported_satellite_vids": _join_vids(supportedSatelliteIds, "ntnSatellite"),
        "supported_earth_station_vids": _join_vids(supportedEarthStationIds, "ntnEarthStation"),
        "plmn_id": plmnId,
        "settlement_mode": settlementMode,
        "registered_at": observedAt,
        "valid_until": validUntil,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_ntn_partner", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "ntnPartnerId": p_id, "status": row["status"]}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.ntn.satellite.register",    single_value=False, timeout_ms=timeout_ms)(task_telecom_ntn_satellite_register)
    worker.task(task_type="telecom.ntn.earthStation.register", single_value=False, timeout_ms=timeout_ms)(task_telecom_ntn_earth_station_register)
    worker.task(task_type="telecom.ntn.cell.provision",        single_value=False, timeout_ms=timeout_ms)(task_telecom_ntn_cell_provision)
    worker.task(task_type="telecom.ntn.ephemeris.record",      single_value=False, timeout_ms=timeout_ms)(task_telecom_ntn_ephemeris_record)
    worker.task(task_type="telecom.ntn.handover.record",       single_value=False, timeout_ms=timeout_ms)(task_telecom_ntn_handover_record)
    worker.task(task_type="telecom.ntn.isl.provision",         single_value=False, timeout_ms=timeout_ms)(task_telecom_ntn_isl_provision)
    worker.task(task_type="telecom.ntn.contact.record",        single_value=False, timeout_ms=timeout_ms)(task_telecom_ntn_contact_record)
    worker.task(task_type="telecom.ntn.partner.register",      single_value=False, timeout_ms=timeout_ms)(task_telecom_ntn_partner_register)
