"""telecom Phase 2 primitives — Resource domain (TMF634 / TMF639 / TMF671).

Eight BPMN service tasks bound to the telecom actor:

  - telecom.spectrum.register
  - telecom.site.register
  - telecom.ranNode.register
  - telecom.asset.register
  - telecom.site.incident
  - telecom.maintenance.schedule
  - telecom.rma.request
  - telecom.kpi.audit

Resource rows live alongside Phase 1 customer/service rows. Edges
(`edge_telecom_*`) connect Resource → Phase 1 service so a `recordSiteIncident`
can fan out into per-service SLA breaches via downstream Phase 1 BPMN
`escalateSlaBreach`.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.resource"

NODE_TYPES = {"gnb", "enb", "du", "cu", "small_cell", "base_station"}
GENERATIONS = {"2g", "3g", "4g", "5g", "5g_sa"}
ASSET_KINDS = {"router", "switch", "antenna", "fiber_cable", "battery", "rectifier", "shelter", "transport_radio"}
INCIDENT_KINDS = {"outage", "degradation", "vandalism", "power_loss", "transport_loss", "weather", "vendor_alarm"}
SEVERITIES = {"minor", "major", "critical"}
MAINT_KINDS = {"preventive", "corrective", "emergency", "vendor_swap", "software_upgrade"}
FAULT_CATS = {"hardware", "firmware", "config", "transport", "power", "other"}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _new_id(prefix: str, *parts: Any) -> str:
    if parts:
        digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]
        return f"{prefix}_{digest}"
    return f"{prefix}_{secrets.token_urlsafe(16).replace('-', '').replace('_', '')[:20]}"


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


def task_telecom_spectrum_register(
    jurisdiction: str = "", band: str = "",
    lowMhz: float = 0.0, highMhz: float = 0.0,
    holderOrgId: str = "", validFrom: str = "", validUntil: str = "",
    licenseId: str = "", region: str = "", technology: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {
        "jurisdiction": jurisdiction, "band": band, "lowMhz": lowMhz, "highMhz": highMhz,
        "holderOrgId": holderOrgId, "validFrom": validFrom, "validUntil": validUntil,
        "callerDid": callerDid,
    }
    _require(payload, ["jurisdiction", "band", "holderOrgId", "validFrom", "validUntil"])
    if float(lowMhz) <= 0 or float(highMhz) <= float(lowMhz):
        raise ValueError("highMhz must be > lowMhz > 0")
    lic_id = licenseId.strip() or _new_id("spec", jurisdiction, band, holderOrgId)
    vid = _vid("spectrumLicense", lic_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "license_id": lic_id, "jurisdiction": jurisdiction, "band": band,
        "low_mhz": float(lowMhz), "high_mhz": float(highMhz),
        "holder_org_id": holderOrgId, "region": region or None,
        "technology": technology or None,
        "valid_from": validFrom, "valid_until": validUntil,
        "status": "active", **_audit(payload),
    }
    _insert("vertex_telecom_spectrum_license", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "licenseId": lic_id, "status": row["status"]}


def task_telecom_site_register(
    name: str = "", latitude: float = 0.0, longitude: float = 0.0,
    jurisdiction: str = "", siteId: str = "", towerOwnerOrgId: str = "",
    height: float | None = None, powerSource: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"name": name, "jurisdiction": jurisdiction, "callerDid": callerDid}
    _require(payload, ["name", "jurisdiction"])
    site_id = siteId.strip() or _new_id("site", name, jurisdiction)
    vid = _vid("cellSite", site_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "site_id": site_id, "name": name,
        "latitude": float(latitude), "longitude": float(longitude),
        "jurisdiction": jurisdiction,
        "tower_owner_org_id": towerOwnerOrgId or None,
        "height_meters": float(height) if height is not None else None,
        "power_source": powerSource or None,
        "status": "active", **_audit(payload),
    }
    _insert("vertex_telecom_cell_site", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "siteId": site_id, "status": row["status"]}


def task_telecom_ran_node_register(
    siteId: str = "", nodeType: str = "", generation: str = "",
    nodeId: str = "", vendor: str = "", model: str = "",
    spectrumLicenseId: str = "", plmnId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"siteId": siteId, "nodeType": nodeType, "generation": generation, "callerDid": callerDid}
    _require(payload, ["siteId", "nodeType", "generation"])
    if nodeType not in NODE_TYPES:
        raise ValueError(f"unsupported nodeType: {nodeType}")
    if generation not in GENERATIONS:
        raise ValueError(f"unsupported generation: {generation}")
    n_id = nodeId.strip() or _new_id("node", siteId, nodeType, generation, vendor)
    vid = _vid("ranNode", n_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "node_id": n_id, "site_vid": _vid("cellSite", siteId),
        "node_type": nodeType, "generation": generation,
        "vendor": vendor or None, "model": model or None,
        "spectrum_license_vid": _vid("spectrumLicense", spectrumLicenseId) if spectrumLicenseId else None,
        "plmn_id": plmnId or None,
        "status": "active", "activated_at": _now_iso(), **_audit(payload),
    }
    _insert("vertex_telecom_ran_node", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "nodeId": n_id, "status": row["status"]}


def task_telecom_asset_register(
    serialNumber: str = "", assetKind: str = "",
    assetId: str = "", vendor: str = "", model: str = "",
    installedSiteId: str = "", installedNodeId: str = "",
    installedAt: str = "", warrantyUntil: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"serialNumber": serialNumber, "assetKind": assetKind, "callerDid": callerDid}
    _require(payload, ["serialNumber", "assetKind"])
    if assetKind not in ASSET_KINDS:
        raise ValueError(f"unsupported assetKind: {assetKind}")
    a_id = assetId.strip() or _new_id("asset", serialNumber)
    vid = _vid("networkAsset", a_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "asset_id": a_id, "serial_number": serialNumber, "asset_kind": assetKind,
        "vendor": vendor or None, "model": model or None,
        "installed_site_vid": _vid("cellSite", installedSiteId) if installedSiteId else None,
        "installed_node_vid": _vid("ranNode", installedNodeId) if installedNodeId else None,
        "installed_at": installedAt or None,
        "warranty_until": warrantyUntil or None,
        "status": "in_service", **_audit(payload),
    }
    _insert("vertex_telecom_network_asset", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "assetId": a_id, "status": row["status"]}


def task_telecom_site_incident(
    siteId: str = "", incidentKind: str = "", severity: str = "",
    detectedAt: str = "", incidentId: str = "", nodeId: str = "",
    resolvedAt: str = "", summary: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"siteId": siteId, "incidentKind": incidentKind, "severity": severity,
               "detectedAt": detectedAt, "callerDid": callerDid}
    _require(payload, ["siteId", "incidentKind", "severity", "detectedAt"])
    if incidentKind not in INCIDENT_KINDS:
        raise ValueError(f"unsupported incidentKind: {incidentKind}")
    if severity not in SEVERITIES:
        raise ValueError(f"unsupported severity: {severity}")
    inc_id = incidentId.strip() or _new_id("inc", siteId, detectedAt, incidentKind)
    vid = _vid("siteIncident", inc_id)
    status = "resolved" if resolvedAt else "open"
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "incident_id": inc_id,
        "site_vid": _vid("cellSite", siteId),
        "node_vid": _vid("ranNode", nodeId) if nodeId else None,
        "incident_kind": incidentKind, "severity": severity,
        "detected_at": detectedAt, "resolved_at": resolvedAt or None,
        "summary": summary or None,
        "status": status, **_audit(payload),
    }
    _insert("vertex_telecom_site_incident", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "incidentId": inc_id, "status": status}


def task_telecom_maintenance_schedule(
    maintenanceKind: str = "", plannedStart: str = "", plannedEnd: str = "",
    windowId: str = "", siteId: str = "", nodeId: str = "", assetId: str = "",
    vendorOrgId: str = "", summary: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"maintenanceKind": maintenanceKind, "plannedStart": plannedStart,
               "plannedEnd": plannedEnd, "callerDid": callerDid}
    _require(payload, ["maintenanceKind", "plannedStart", "plannedEnd"])
    if maintenanceKind not in MAINT_KINDS:
        raise ValueError(f"unsupported maintenanceKind: {maintenanceKind}")
    w_id = windowId.strip() or _new_id("mwin", plannedStart, maintenanceKind, siteId or nodeId or assetId or "global")
    vid = _vid("maintenanceWindow", w_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "window_id": w_id,
        "site_vid": _vid("cellSite", siteId) if siteId else None,
        "node_vid": _vid("ranNode", nodeId) if nodeId else None,
        "asset_vid": _vid("networkAsset", assetId) if assetId else None,
        "maintenance_kind": maintenanceKind,
        "planned_start": plannedStart, "planned_end": plannedEnd,
        "vendor_org_id": vendorOrgId or None,
        "summary": summary or None,
        "status": "planned", **_audit(payload),
    }
    _insert("vertex_telecom_maintenance_window", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "windowId": w_id, "status": row["status"]}


def task_telecom_rma_request(
    assetId: str = "", vendorOrgId: str = "",
    faultCategory: str = "", openedAt: str = "",
    rmaId: str = "", faultDescription: str = "", expectedReturnAt: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"assetId": assetId, "vendorOrgId": vendorOrgId,
               "faultCategory": faultCategory, "openedAt": openedAt,
               "callerDid": callerDid}
    _require(payload, ["assetId", "vendorOrgId", "faultCategory", "openedAt"])
    if faultCategory not in FAULT_CATS:
        raise ValueError(f"unsupported faultCategory: {faultCategory}")
    r_id = rmaId.strip() or _new_id("rma", assetId, vendorOrgId, openedAt)
    vid = _vid("rmaCase", r_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "rma_id": r_id,
        "asset_vid": _vid("networkAsset", assetId),
        "vendor_org_id": vendorOrgId,
        "fault_category": faultCategory,
        "fault_description": faultDescription or None,
        "opened_at": openedAt,
        "expected_return_at": expectedReturnAt or None,
        "closed_at": None,
        "status": "open", **_audit(payload),
    }
    _insert("vertex_telecom_rma_case", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "rmaId": r_id, "status": row["status"]}


def task_telecom_kpi_audit(
    nodeId: str = "", metric: str = "",
    value: float = 0.0, sampledAt: str = "",
    sampleId: str = "", unit: str = "",
    slaThreshold: float | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"nodeId": nodeId, "metric": metric, "sampledAt": sampledAt, "callerDid": callerDid}
    _require(payload, ["nodeId", "metric", "sampledAt"])
    val = float(value)
    threshold = float(slaThreshold) if slaThreshold is not None else None
    breach = bool(threshold is not None and val > threshold)
    s_id = sampleId.strip() or _new_id("kpi", nodeId, metric, sampledAt)
    vid = _vid("kpiSample", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "sample_id": s_id, "node_vid": _vid("ranNode", nodeId),
        "metric": metric, "value": val, "unit": unit or None,
        "sampled_at": sampledAt, "sla_threshold": threshold,
        "breach": breach, "status": "recorded", **_audit(payload),
    }
    _insert("vertex_telecom_kpi_sample", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "sampleId": s_id, "breach": breach, "status": row["status"]}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.spectrum.register",     single_value=False, timeout_ms=timeout_ms)(task_telecom_spectrum_register)
    worker.task(task_type="telecom.site.register",         single_value=False, timeout_ms=timeout_ms)(task_telecom_site_register)
    worker.task(task_type="telecom.ranNode.register",      single_value=False, timeout_ms=timeout_ms)(task_telecom_ran_node_register)
    worker.task(task_type="telecom.asset.register",        single_value=False, timeout_ms=timeout_ms)(task_telecom_asset_register)
    worker.task(task_type="telecom.site.incident",         single_value=False, timeout_ms=timeout_ms)(task_telecom_site_incident)
    worker.task(task_type="telecom.maintenance.schedule",  single_value=False, timeout_ms=timeout_ms)(task_telecom_maintenance_schedule)
    worker.task(task_type="telecom.rma.request",           single_value=False, timeout_ms=timeout_ms)(task_telecom_rma_request)
    worker.task(task_type="telecom.kpi.audit",             single_value=False, timeout_ms=timeout_ms)(task_telecom_kpi_audit)
