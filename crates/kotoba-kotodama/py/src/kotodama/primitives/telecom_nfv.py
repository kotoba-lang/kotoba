"""telecom Phase 12 primitives — SDN-NFV (ETSI MANO + ONAP).

Eight BPMN service tasks:

  - telecom.nfv.nsd.onboard
  - telecom.nfv.vnfd.onboard
  - telecom.nfv.ns.instantiate
  - telecom.nfv.vnf.instantiate
  - telecom.nfv.vnf.scale
  - telecom.nfv.vnf.heal
  - telecom.nfv.sdn.flow
  - telecom.nfv.ns.terminate

Discipline:
  - Descriptor / package bodies persist as sha256:|sha384:|sha512: hash +
    optional vault:// pointer.
  - SDN flow match/action persisted only as hash.
  - `terminateNetworkService` mutates ns row; computes `lifetime_seconds`.
  - `scaleVnf` computes `delta = to_instance_count - from_instance_count`.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.nfv"

DESCRIPTOR_FORMATS = {"tosca", "yang", "heat", "helm"}
VNF_KINDS = {"vm_vnf", "container_cnf", "hybrid"}
SCALE_KINDS = {"horizontal", "vertical"}
SCALE_DIRECTIONS = {"scale_out", "scale_in", "scale_up", "scale_down"}
SCALE_TRIGGERS = {"manual", "policy", "capacity_forecast", "nwdaf_load", "alarm"}
HEAL_CAUSES = {"sw_failure", "hw_failure", "sla_breach", "operator_request", "alarm_correlation", "policy"}
HEAL_KINDS = {"restart", "reinstantiate", "live_migrate", "snapshot_rollback"}
SOUTHBOUND_PROTOCOLS = {"openflow", "p4runtime", "netconf", "ovsdb", "gnmi"}
FLOW_ACTIONS = {"install", "modify", "delete"}
TERMINATION_KINDS = {"graceful", "forceful", "scheduled", "operator_request"}


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


def task_telecom_nfv_nsd_onboard(
    vendor: str = "", name: str = "", version: str = "",
    descriptorFormat: str = "", constituentVnfdIds: Any = None,
    packageHash: str = "", observedAt: str = "",
    nsdId: str = "", virtualLinks: Any = None, packageRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"vendor": vendor, "name": name, "version": version,
               "descriptorFormat": descriptorFormat,
               "constituentVnfdIds": constituentVnfdIds,
               "packageHash": packageHash, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["vendor", "name", "version", "descriptorFormat",
                       "constituentVnfdIds", "packageHash", "observedAt"])
    if descriptorFormat not in DESCRIPTOR_FORMATS:
        raise ValueError(f"unsupported descriptorFormat: {descriptorFormat}")
    if not isinstance(constituentVnfdIds, (list, tuple)) or not constituentVnfdIds:
        raise ValueError("constituentVnfdIds must be a non-empty list")
    _require_hash_prefix(packageHash, "packageHash")
    _require_vault_ref(packageRef, "packageRef")
    n_id = nsdId.strip() or _new_id("nsd", vendor, name, version)
    vid = _vid("nfvNsd", n_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "nsd_id": n_id,
        "vendor": vendor, "name": name, "version": version,
        "descriptor_format": descriptorFormat,
        "constituent_vnfd_ids": _join(constituentVnfdIds),
        "virtual_links": _join(virtualLinks),
        "package_hash": packageHash,
        "package_ref": packageRef or None,
        "onboarded_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_nfv_nsd", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "nsdId": n_id, "status": row["status"]}


def task_telecom_nfv_vnfd_onboard(
    vendor: str = "", name: str = "", version: str = "",
    vnfKind: str = "", descriptorFormat: str = "",
    deploymentFlavors: Any = None,
    packageHash: str = "", observedAt: str = "",
    vnfdId: str = "", requiredVims: Any = None, packageRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"vendor": vendor, "name": name, "version": version,
               "vnfKind": vnfKind, "descriptorFormat": descriptorFormat,
               "deploymentFlavors": deploymentFlavors,
               "packageHash": packageHash, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["vendor", "name", "version", "vnfKind",
                       "descriptorFormat", "deploymentFlavors",
                       "packageHash", "observedAt"])
    if vnfKind not in VNF_KINDS:
        raise ValueError(f"unsupported vnfKind: {vnfKind}")
    if descriptorFormat not in DESCRIPTOR_FORMATS:
        raise ValueError(f"unsupported descriptorFormat: {descriptorFormat}")
    if not isinstance(deploymentFlavors, (list, tuple)) or not deploymentFlavors:
        raise ValueError("deploymentFlavors must be a non-empty list")
    _require_hash_prefix(packageHash, "packageHash")
    _require_vault_ref(packageRef, "packageRef")
    v_id = vnfdId.strip() or _new_id("vnfd", vendor, name, version)
    vid = _vid("nfvVnfd", v_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "vnfd_id": v_id,
        "vendor": vendor, "name": name, "version": version,
        "vnf_kind": vnfKind, "descriptor_format": descriptorFormat,
        "deployment_flavors": _join(deploymentFlavors),
        "required_vims": _join(requiredVims),
        "package_hash": packageHash,
        "package_ref": packageRef or None,
        "onboarded_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_nfv_vnfd", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "vnfdId": v_id, "status": row["status"]}


def task_telecom_nfv_ns_instantiate(
    nsdId: str = "", nfvoNfId: str = "", vimIds: Any = None,
    deploymentFlavor: str = "", observedAt: str = "",
    nsId: str = "", snssai: str = "", dnn: str = "", parameters: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"nsdId": nsdId, "nfvoNfId": nfvoNfId, "vimIds": vimIds,
               "deploymentFlavor": deploymentFlavor,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["nsdId", "nfvoNfId", "vimIds",
                       "deploymentFlavor", "observedAt"])
    if not isinstance(vimIds, (list, tuple)) or not vimIds:
        raise ValueError("vimIds must be a non-empty list")
    n_id = nsId.strip() or _new_id("ns", nsdId, deploymentFlavor, observedAt)
    vid = _vid("nfvNs", n_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "ns_id": n_id,
        "nsd_vid": _vid("nfvNsd", nsdId),
        "nfvo_nf_vid": _vid("nfInstance", nfvoNfId),
        "vim_ids": _join(vimIds),
        "snssai": snssai or None,
        "dnn": dnn or None,
        "deployment_flavor": deploymentFlavor,
        "parameters": parameters or None,
        "instantiated_at": observedAt,
        "terminated_at": None, "lifetime_seconds": None,
        "termination_kind": None, "termination_reason": None, "terminated_by": None,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_nfv_ns", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "nsId": n_id, "status": row["status"]}


def task_telecom_nfv_vnf_instantiate(
    nsId: str = "", vnfdId: str = "", vnfmNfId: str = "", vimId: str = "",
    deploymentFlavor: str = "", observedAt: str = "",
    vnfId: str = "",
    requestedVcpus: int | None = None, requestedMemoryGib: float | None = None,
    mappedNfInstanceId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"nsId": nsId, "vnfdId": vnfdId, "vnfmNfId": vnfmNfId,
               "vimId": vimId, "deploymentFlavor": deploymentFlavor,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["nsId", "vnfdId", "vnfmNfId", "vimId",
                       "deploymentFlavor", "observedAt"])
    v_id = vnfId.strip() or _new_id("vnf", nsId, vnfdId, vimId, observedAt)
    vid = _vid("nfvVnf", v_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "vnf_id": v_id,
        "ns_vid": _vid("nfvNs", nsId),
        "vnfd_vid": _vid("nfvVnfd", vnfdId),
        "vnfm_nf_vid": _vid("nfInstance", vnfmNfId),
        "vim_id": vimId,
        "deployment_flavor": deploymentFlavor,
        "requested_vcpus": int(requestedVcpus) if requestedVcpus is not None else None,
        "requested_memory_gib": float(requestedMemoryGib) if requestedMemoryGib is not None else None,
        "mapped_nf_instance_vid": _vid("nfInstance", mappedNfInstanceId) if mappedNfInstanceId else None,
        "instantiated_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_nfv_vnf", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "vnfId": v_id, "status": row["status"]}


def task_telecom_nfv_vnf_scale(
    vnfId: str = "", scaleKind: str = "", scaleDirection: str = "",
    fromInstanceCount: int = 0, toInstanceCount: int = 0,
    triggerKind: str = "", observedAt: str = "",
    scaleEventId: str = "", aspectId: str = "", triggerVid: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"vnfId": vnfId, "scaleKind": scaleKind,
               "scaleDirection": scaleDirection,
               "triggerKind": triggerKind, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["vnfId", "scaleKind", "scaleDirection",
                       "triggerKind", "observedAt"])
    if scaleKind not in SCALE_KINDS:
        raise ValueError(f"unsupported scaleKind: {scaleKind}")
    if scaleDirection not in SCALE_DIRECTIONS:
        raise ValueError(f"unsupported scaleDirection: {scaleDirection}")
    if triggerKind not in SCALE_TRIGGERS:
        raise ValueError(f"unsupported triggerKind: {triggerKind}")
    f = int(fromInstanceCount)
    t = int(toInstanceCount)
    if f < 0 or t < 0:
        raise ValueError("instance counts must be non-negative")
    delta = t - f
    s_id = scaleEventId.strip() or _new_id("scl", vnfId, scaleDirection, observedAt)
    vid = _vid("nfvScaleEvent", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "scale_event_id": s_id,
        "vnf_vid": _vid("nfvVnf", vnfId),
        "scale_kind": scaleKind,
        "scale_direction": scaleDirection,
        "aspect_id": aspectId or None,
        "from_instance_count": f,
        "to_instance_count": t,
        "delta": delta,
        "trigger_kind": triggerKind,
        "trigger_vid": triggerVid or None,
        "observed_at": observedAt,
        "status": "completed",
        **_audit(payload),
    }
    _insert("vertex_telecom_nfv_scale_event", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "scaleEventId": s_id,
            "delta": delta, "status": row["status"]}


def task_telecom_nfv_vnf_heal(
    vnfId: str = "", healCause: str = "", healKind: str = "",
    observedAt: str = "",
    healEventId: str = "", alarmVid: str = "",
    recreateAffectedInstances: bool | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"vnfId": vnfId, "healCause": healCause, "healKind": healKind,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["vnfId", "healCause", "healKind", "observedAt"])
    if healCause not in HEAL_CAUSES:
        raise ValueError(f"unsupported healCause: {healCause}")
    if healKind not in HEAL_KINDS:
        raise ValueError(f"unsupported healKind: {healKind}")
    h_id = healEventId.strip() or _new_id("heal", vnfId, healKind, observedAt)
    vid = _vid("nfvHealEvent", h_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "heal_event_id": h_id,
        "vnf_vid": _vid("nfvVnf", vnfId),
        "heal_cause": healCause,
        "heal_kind": healKind,
        "alarm_vid": alarmVid or None,
        "recreate_affected_instances": bool(recreateAffectedInstances) if recreateAffectedInstances is not None else None,
        "observed_at": observedAt,
        "status": "completed",
        **_audit(payload),
    }
    _insert("vertex_telecom_nfv_heal_event", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "healEventId": h_id, "status": row["status"]}


def task_telecom_nfv_sdn_flow(
    sdnControllerId: str = "", southboundProtocol: str = "",
    switchDpid: str = "", tableId: int = 0, priority: int = 0,
    matchHash: str = "", actionHash: str = "", action: str = "",
    observedAt: str = "",
    flowId: str = "", vnfId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"sdnControllerId": sdnControllerId,
               "southboundProtocol": southboundProtocol,
               "switchDpid": switchDpid,
               "tableId": tableId, "priority": priority,
               "matchHash": matchHash, "actionHash": actionHash,
               "action": action, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["sdnControllerId", "southboundProtocol", "switchDpid",
                       "matchHash", "actionHash", "action", "observedAt"])
    if southboundProtocol not in SOUTHBOUND_PROTOCOLS:
        raise ValueError(f"unsupported southboundProtocol: {southboundProtocol}")
    if action not in FLOW_ACTIONS:
        raise ValueError(f"unsupported action: {action}")
    _require_hash_prefix(matchHash, "matchHash")
    _require_hash_prefix(actionHash, "actionHash")
    f_id = flowId.strip() or _new_id("sdnflow", switchDpid, matchHash[:16], observedAt)
    vid = _vid("nfvSdnFlow", f_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "flow_id": f_id,
        "sdn_controller_id": sdnControllerId,
        "southbound_protocol": southboundProtocol,
        "switch_dpid": switchDpid,
        "table_id": int(tableId),
        "priority": int(priority),
        "match_hash": matchHash,
        "action_hash": actionHash,
        "action": action,
        "vnf_vid": _vid("nfvVnf", vnfId) if vnfId else None,
        "observed_at": observedAt,
        "status": "installed" if action == "install" else action,
        **_audit(payload),
    }
    _insert("vertex_telecom_nfv_sdn_flow", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "flowId": f_id, "status": row["status"]}


def task_telecom_nfv_ns_terminate(
    nsId: str = "", terminationKind: str = "",
    terminatedBy: str = "", terminatedAt: str = "",
    terminationReason: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"nsId": nsId, "terminationKind": terminationKind,
               "terminatedBy": terminatedBy, "terminatedAt": terminatedAt,
               "callerDid": callerDid}
    _require(payload, ["nsId", "terminationKind", "terminatedBy", "terminatedAt"])
    if terminationKind not in TERMINATION_KINDS:
        raise ValueError(f"unsupported terminationKind: {terminationKind}")
    vid = _vid("nfvNs", nsId)
    lifetime = None
    if not dryRun:
        ns_row = get_kotoba_client().select_first_where("vertex_telecom_nfv_ns", "vertex_id", vid)
        if ns_row and ns_row.get("instantiated_at"):
            instantiated_at = datetime.fromisoformat(ns_row["instantiated_at"]).replace(tzinfo=UTC)
            terminated_at_dt = datetime.fromisoformat(terminatedAt).replace(tzinfo=UTC)
            lifetime_delta = terminated_at_dt - instantiated_at
            lifetime = lifetime_delta.total_seconds()

        updated_ns_row = {
            "vertex_id": vid,
            "terminated_at": terminatedAt,
            "termination_kind": terminationKind,
            "termination_reason": terminationReason or None,
            "terminated_by": terminatedBy,
            "lifetime_seconds": lifetime,
            "status": "terminated",
        }
        # R0: This is an UPSERT on vertex_id to update the existing ns row
        get_kotoba_client().insert_row("vertex_telecom_nfv_ns", updated_ns_row)

    return {"ok": True, "vertexId": vid, "nsId": nsId,
            "lifetimeSeconds": lifetime, "status": "terminated"}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.nfv.nsd.onboard",      single_value=False, timeout_ms=timeout_ms)(task_telecom_nfv_nsd_onboard)
    worker.task(task_type="telecom.nfv.vnfd.onboard",     single_value=False, timeout_ms=timeout_ms)(task_telecom_nfv_vnfd_onboard)
    worker.task(task_type="telecom.nfv.ns.instantiate",   single_value=False, timeout_ms=timeout_ms * 2)(task_telecom_nfv_ns_instantiate)
    worker.task(task_type="telecom.nfv.vnf.instantiate",  single_value=False, timeout_ms=timeout_ms * 2)(task_telecom_nfv_vnf_instantiate)
    worker.task(task_type="telecom.nfv.vnf.scale",        single_value=False, timeout_ms=timeout_ms)(task_telecom_nfv_vnf_scale)
    worker.task(task_type="telecom.nfv.vnf.heal",         single_value=False, timeout_ms=timeout_ms * 2)(task_telecom_nfv_vnf_heal)
    worker.task(task_type="telecom.nfv.sdn.flow",         single_value=False, timeout_ms=timeout_ms)(task_telecom_nfv_sdn_flow)
    worker.task(task_type="telecom.nfv.ns.terminate",     single_value=False, timeout_ms=timeout_ms)(task_telecom_nfv_ns_terminate)
