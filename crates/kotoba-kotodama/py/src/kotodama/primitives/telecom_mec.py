"""telecom Phase 10 primitives — MEC + 3GPP EAS edge plane.

Eight BPMN service tasks bound to the telecom actor:

  - telecom.mec.host.register
  - telecom.mec.app.onboard
  - telecom.mec.eas.instantiate
  - telecom.mec.eas.discover
  - telecom.mec.eas.relocate
  - telecom.mec.service.call
  - telecom.mec.federation.register
  - telecom.mec.eas.terminate

Discipline:
  - App / state package bodies persisted only as sha256:|sha384:|sha512:
    hash + optional vault:// pointer. EAS payload bodies never persist.
  - UE identifiers persisted only as sha256 hash (Tier-3 PII).
  - `terminateEdgeAppInstance` mutates the existing eas row and computes
    `lifetime_seconds = EXTRACT(EPOCH FROM terminated_at - instantiated_at)`.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.mec"

LATENCY_CLASSES = {"urllc", "embb", "iot", "best_effort"}
DISCOVERY_STRATEGIES = {"nearest", "lowest_load", "preferred_provider", "round_robin", "policy_driven"}
RELOCATION_TRIGGERS = {"ue_mobility", "load_balance", "capacity_breach",
                       "host_failure", "operator_request", "policy_driven"}
ACR_MODES = {"s8", "s8s9", "s8c", "stateless", "stateful"}
METHOD_KINDS = {"GET", "POST", "PUT", "PATCH", "DELETE", "GRPC_UNARY", "GRPC_STREAM"}
FEDERATION_KINDS = {"bilateral", "hub_spoke", "mesh"}
BILLING_MODES = {"bill_back", "settlement", "free", "consumption_based"}
TERMINATION_KINDS = {"graceful", "forceful", "scheduled", "host_decommission", "operator_request"}


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


def task_telecom_mec_host_register(
    oCloudId: str = "", vendor: str = "", hostFqdn: str = "",
    latitude: float = 0.0, longitude: float = 0.0, edgeZone: str = "",
    plmnId: str = "", observedAt: str = "",
    hostId: str = "", supportedVims: Any = None,
    cpuCapacity: int | None = None, memoryCapacityGib: float | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"oCloudId": oCloudId, "vendor": vendor, "hostFqdn": hostFqdn,
               "edgeZone": edgeZone, "plmnId": plmnId,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["oCloudId", "vendor", "hostFqdn", "edgeZone",
                       "plmnId", "observedAt"])
    h_id = hostId.strip() or _new_id("mecho", oCloudId, hostFqdn)
    vid = _vid("mecHost", h_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "host_id": h_id, "o_cloud_id": oCloudId,
        "vendor": vendor, "host_fqdn": hostFqdn,
        "latitude": float(latitude), "longitude": float(longitude),
        "edge_zone": edgeZone, "plmn_id": plmnId,
        "supported_vims": _join(supportedVims),
        "cpu_capacity": int(cpuCapacity) if cpuCapacity is not None else None,
        "memory_capacity_gib": float(memoryCapacityGib) if memoryCapacityGib is not None else None,
        "registered_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_mec_host", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "hostId": h_id, "status": row["status"]}


def task_telecom_mec_app_onboard(
    vendor: str = "", name: str = "", version: str = "",
    appDescriptor: str = "", latencyClass: str = "",
    packageHash: str = "", observedAt: str = "",
    appPackageId: str = "", requiredEases: Any = None,
    requestedFlavor: str = "", packageRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"vendor": vendor, "name": name, "version": version,
               "appDescriptor": appDescriptor, "latencyClass": latencyClass,
               "packageHash": packageHash, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["vendor", "name", "version", "appDescriptor",
                       "latencyClass", "packageHash", "observedAt"])
    if latencyClass not in LATENCY_CLASSES:
        raise ValueError(f"unsupported latencyClass: {latencyClass}")
    _require_hash_prefix(packageHash, "packageHash")
    _require_vault_ref(packageRef, "packageRef")
    p_id = appPackageId.strip() or _new_id("mecapp", vendor, name, version)
    vid = _vid("mecAppPackage", p_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "app_package_id": p_id,
        "vendor": vendor, "name": name, "version": version,
        "app_descriptor": appDescriptor,
        "required_eases": _join(requiredEases),
        "latency_class": latencyClass,
        "requested_flavor": requestedFlavor or None,
        "package_hash": packageHash,
        "package_ref": packageRef or None,
        "onboarded_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_mec_app_package", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "appPackageId": p_id, "status": row["status"]}


def task_telecom_mec_eas_instantiate(
    appPackageId: str = "", hostId: str = "", easProviderId: str = "",
    easFqdn: str = "", observedAt: str = "",
    easId: str = "", snssai: str = "", dnn: str = "", easIpv4: str = "",
    requestedFlavor: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"appPackageId": appPackageId, "hostId": hostId,
               "easProviderId": easProviderId, "easFqdn": easFqdn,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["appPackageId", "hostId", "easProviderId",
                       "easFqdn", "observedAt"])
    e_id = easId.strip() or _new_id("eas", appPackageId, hostId, observedAt)
    vid = _vid("mecEas", e_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "eas_id": e_id,
        "app_package_vid": _vid("mecAppPackage", appPackageId),
        "host_vid": _vid("mecHost", hostId),
        "eas_provider_id": easProviderId,
        "snssai": snssai or None,
        "dnn": dnn or None,
        "eas_fqdn": easFqdn,
        "eas_ipv4": easIpv4 or None,
        "requested_flavor": requestedFlavor or None,
        "instantiated_at": observedAt,
        "terminated_at": None, "lifetime_seconds": None,
        "termination_kind": None, "termination_reason": None, "terminated_by": None,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_mec_eas", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "easId": e_id, "status": row["status"]}


def task_telecom_mec_eas_discover(
    eesId: str = "", requestingAcId: str = "", ueIdHash: str = "",
    easProviderId: str = "", requestedAppId: str = "",
    selectedEasId: str = "", observedAt: str = "",
    discoveryId: str = "", ueLocationCellId: str = "",
    candidateEasIds: Any = None, selectionStrategy: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"eesId": eesId, "requestingAcId": requestingAcId,
               "ueIdHash": ueIdHash, "easProviderId": easProviderId,
               "requestedAppId": requestedAppId,
               "selectedEasId": selectedEasId,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["eesId", "requestingAcId", "ueIdHash",
                       "easProviderId", "requestedAppId",
                       "selectedEasId", "observedAt"])
    _require_hash_prefix(ueIdHash, "ueIdHash")
    if selectionStrategy and selectionStrategy not in DISCOVERY_STRATEGIES:
        raise ValueError(f"unsupported selectionStrategy: {selectionStrategy}")
    candidates = list(candidateEasIds) if isinstance(candidateEasIds, (list, tuple)) else []
    d_id = discoveryId.strip() or _new_id("eesdsc", requestingAcId, requestedAppId, observedAt)
    vid = _vid("mecEasDiscovery", d_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "discovery_id": d_id,
        "ees_id": eesId,
        "requesting_ac_id": requestingAcId,
        "ue_id_hash": ueIdHash,
        "ue_location_cell_id": ueLocationCellId or None,
        "eas_provider_id": easProviderId,
        "requested_app_id": requestedAppId,
        "candidate_count": len(candidates),
        "candidate_eas_ids": _join(candidates),
        "selected_eas_vid": _vid("mecEas", selectedEasId),
        "selection_strategy": selectionStrategy or None,
        "observed_at": observedAt,
        "status": "selected",
        **_audit(payload),
    }
    _insert("vertex_telecom_mec_eas_discovery", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "discoveryId": d_id,
            "candidateCount": len(candidates), "status": row["status"]}


def task_telecom_mec_eas_relocate(
    easId: str = "", fromHostId: str = "", toHostId: str = "",
    triggerKind: str = "", acrMode: str = "", observedAt: str = "",
    relocationId: str = "", triggerVid: str = "",
    statePackageHash: str = "", statePackageRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"easId": easId, "fromHostId": fromHostId, "toHostId": toHostId,
               "triggerKind": triggerKind, "acrMode": acrMode,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["easId", "fromHostId", "toHostId",
                       "triggerKind", "acrMode", "observedAt"])
    if triggerKind not in RELOCATION_TRIGGERS:
        raise ValueError(f"unsupported triggerKind: {triggerKind}")
    if acrMode not in ACR_MODES:
        raise ValueError(f"unsupported acrMode: {acrMode}")
    if statePackageHash:
        _require_hash_prefix(statePackageHash, "statePackageHash")
    _require_vault_ref(statePackageRef, "statePackageRef")
    r_id = relocationId.strip() or _new_id("easmv", easId, fromHostId, toHostId, observedAt)
    vid = _vid("mecEasRelocation", r_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "relocation_id": r_id,
        "eas_vid": _vid("mecEas", easId),
        "from_host_vid": _vid("mecHost", fromHostId),
        "to_host_vid": _vid("mecHost", toHostId),
        "trigger_kind": triggerKind,
        "trigger_vid": triggerVid or None,
        "acr_mode": acrMode,
        "state_package_hash": statePackageHash or None,
        "state_package_ref": statePackageRef or None,
        "observed_at": observedAt,
        "status": "in_progress",
        **_audit(payload),
    }
    _insert("vertex_telecom_mec_eas_relocation", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "relocationId": r_id, "status": row["status"]}


def task_telecom_mec_service_call(
    easId: str = "", ueIdHash: str = "", methodKind: str = "",
    statusCode: int = 0, observedAt: str = "",
    callId: str = "", sessionVid: str = "",
    latencyMs: float | None = None,
    payloadInBytes: int | None = None, payloadOutBytes: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"easId": easId, "ueIdHash": ueIdHash,
               "methodKind": methodKind, "statusCode": statusCode,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["easId", "ueIdHash", "methodKind", "statusCode", "observedAt"])
    if methodKind not in METHOD_KINDS:
        raise ValueError(f"unsupported methodKind: {methodKind}")
    code = int(statusCode)
    if code < 0:
        raise ValueError("statusCode must be >= 0")
    _require_hash_prefix(ueIdHash, "ueIdHash")
    c_id = callId.strip() or _new_id("eascl", easId, methodKind, observedAt)
    vid = _vid("mecServiceCall", c_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "call_id": c_id,
        "eas_vid": _vid("mecEas", easId),
        "ue_id_hash": ueIdHash,
        "session_vid": sessionVid or None,
        "method_kind": methodKind,
        "status_code": code,
        "latency_ms": float(latencyMs) if latencyMs is not None else None,
        "payload_in_bytes": int(payloadInBytes) if payloadInBytes is not None else None,
        "payload_out_bytes": int(payloadOutBytes) if payloadOutBytes is not None else None,
        "observed_at": observedAt,
        "status": "served" if 0 < code < 400 else ("recorded" if code == 0 else "failed"),
        **_audit(payload),
    }
    _insert("vertex_telecom_mec_service_call", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "callId": c_id, "status": row["status"]}


def task_telecom_mec_federation_register(
    partnerOperatorId: str = "", agreementId: str = "",
    federationKind: str = "", billingMode: str = "",
    validUntil: str = "", observedAt: str = "",
    federationId: str = "",
    exposedZones: Any = None, exposedAppCatalog: Any = None,
    contractRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"partnerOperatorId": partnerOperatorId,
               "agreementId": agreementId,
               "federationKind": federationKind,
               "billingMode": billingMode,
               "validUntil": validUntil, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["partnerOperatorId", "agreementId",
                       "federationKind", "billingMode",
                       "validUntil", "observedAt"])
    if federationKind not in FEDERATION_KINDS:
        raise ValueError(f"unsupported federationKind: {federationKind}")
    if billingMode not in BILLING_MODES:
        raise ValueError(f"unsupported billingMode: {billingMode}")
    _require_vault_ref(contractRef, "contractRef")
    f_id = federationId.strip() or _new_id("mecfed", partnerOperatorId, agreementId, observedAt)
    vid = _vid("mecFederation", f_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "federation_id": f_id,
        "partner_operator_id": partnerOperatorId,
        "agreement_vid": _vid("interconnectAgreement", agreementId),
        "federation_kind": federationKind,
        "exposed_zones": _join(exposedZones),
        "exposed_app_catalog": _join(exposedAppCatalog),
        "billing_mode": billingMode,
        "contract_ref": contractRef or None,
        "established_at": observedAt,
        "valid_until": validUntil,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_mec_federation", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "federationId": f_id, "status": row["status"]}


def task_telecom_mec_eas_terminate(
    easId: str = "", terminationKind: str = "",
    terminatedBy: str = "", terminatedAt: str = "",
    terminationReason: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"easId": easId, "terminationKind": terminationKind,
               "terminatedBy": terminatedBy, "terminatedAt": terminatedAt,
               "callerDid": callerDid}
    _require(payload, ["easId", "terminationKind", "terminatedBy", "terminatedAt"])
    if terminationKind not in TERMINATION_KINDS:
        raise ValueError(f"unsupported terminationKind: {terminationKind}")
    vid = _vid("mecEas", easId)
    lifetime = None
    if not dryRun:
        # R0: Replaced SQL UPDATE with Python logic + kotoba client upsert.
        #     First, fetch the existing record to get 'instantiated_at'.
        #     Then calculate 'lifetime_seconds' in Python.
        #     Finally, perform an UPSERT (update) using insert_row.
        eas_record = get_kotoba_client().select_first_where(
            "vertex_telecom_mec_eas",
            "vertex_id",
            vid
        )

        if eas_record:
            # Calculate lifetime_seconds
            instantiated_at_str = eas_record.get("instantiated_at")
            current_terminated_at_dt = datetime.fromisoformat(terminatedAt).replace(tzinfo=timezone.utc)

            calculated_lifetime = None
            if instantiated_at_str:
                instantiated_at_dt = datetime.fromisoformat(instantiated_at_str).replace(tzinfo=timezone.utc)
                calculated_lifetime = (current_terminated_at_dt - instantiated_at_dt).total_seconds()

            # Prepare the updated row dictionary
            eas_record.update({
                "terminated_at": terminatedAt,
                "termination_kind": terminationKind,
                "termination_reason": terminationReason or None,
                "terminated_by": terminatedBy,
                "lifetime_seconds": calculated_lifetime,
                "status": "terminated",
            })

            # Perform the upsert (which acts as an update here)
            updated_eas_record = get_kotoba_client().insert_row("vertex_telecom_mec_eas", eas_record)
            lifetime = updated_eas_record.get("lifetime_seconds")
        else:
            # If the record doesn't exist, it's an error scenario, similar to what the original
            # SQL UPDATE would have done if the WHERE clause didn't match.
            # Here, we will just proceed with lifetime=None and let the return dict reflect that.
            # This matches the behavior of the original code where if row is None, lifetime remains None.
            pass
    return {"ok": True, "vertexId": vid, "easId": easId,
            "lifetimeSeconds": lifetime, "status": "terminated"}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.mec.host.register",       single_value=False, timeout_ms=timeout_ms)(task_telecom_mec_host_register)
    worker.task(task_type="telecom.mec.app.onboard",         single_value=False, timeout_ms=timeout_ms)(task_telecom_mec_app_onboard)
    worker.task(task_type="telecom.mec.eas.instantiate",     single_value=False, timeout_ms=timeout_ms * 2)(task_telecom_mec_eas_instantiate)
    worker.task(task_type="telecom.mec.eas.discover",        single_value=False, timeout_ms=timeout_ms)(task_telecom_mec_eas_discover)
    worker.task(task_type="telecom.mec.eas.relocate",        single_value=False, timeout_ms=timeout_ms * 2)(task_telecom_mec_eas_relocate)
    worker.task(task_type="telecom.mec.service.call",        single_value=False, timeout_ms=timeout_ms)(task_telecom_mec_service_call)
    worker.task(task_type="telecom.mec.federation.register", single_value=False, timeout_ms=timeout_ms)(task_telecom_mec_federation_register)
    worker.task(task_type="telecom.mec.eas.terminate",       single_value=False, timeout_ms=timeout_ms)(task_telecom_mec_eas_terminate)
