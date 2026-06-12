"""telecom Phase 9 primitives — Open RAN (O-RAN Alliance).

Eight BPMN service tasks bound to the telecom actor:

  - telecom.oran.smo.register     (SMO node + Non-RT RIC + O1/O2 endpoints)
  - telecom.oran.rapp.onboard     (rApp → SMO/Non-RT RIC)
  - telecom.oran.xapp.deploy      (xApp → Near-RT RIC)
  - telecom.oran.a1.policy        (A1 policy instance: rApp → Near-RT RIC)
  - telecom.oran.e2.subscribe     (E2 service subscription: xApp → E2 Node)
  - telecom.oran.e2.indication    (E2 INDICATION audit trail)
  - telecom.oran.o1.config        (O1 NETCONF/RESTCONF YANG push: SMO → NF)
  - telecom.oran.o2.provision     (O2-IMS / O2-DMS O-Cloud provisioning)

Package / configuration / policy bodies are persisted only as
`sha256:|sha384:|sha512:` hashes plus optional `vault://` pointers.
E2 ASN.1 PER messages: header_hash + message_hash only.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.oran"

A1_USE_CASES = {"qos_assurance", "traffic_steering", "energy_saving",
                "anomaly_detection", "slice_assurance", "rrm_optimization"}
A1_SCOPE_KINDS = {"ueGroup", "snssai", "cellSite", "ranNode", "service"}
A1_ACTIONS = {"create", "modify", "delete"}
E2_SERVICE_MODELS = {"e2sm-kpm", "e2sm-rc", "e2sm-ni", "e2sm-ccc"}
E2_TRIGGERS = {"periodic", "ueid", "cell", "upon_change"}
E2_ACTION_KINDS = {"report", "insert", "policy", "control"}
E2_INDICATION_TYPES = {"report", "insert", "control_outcome"}
O1_TARGET_KINDS = {"o-cu-cp", "o-cu-up", "o-du", "o-ru", "near-rt-ric", "smo"}
O1_TRANSPORTS = {"netconf", "restconf", "ves"}
O1_OPERATIONS = {"create", "merge", "replace", "delete"}
O2_INTERFACE_KINDS = {"o2-ims", "o2-dms"}
O2_RESOURCE_KINDS = {"compute_node", "storage_pool", "network_fabric",
                     "deployment", "deployment_manager", "subscription"}
O2_DEPLOYMENT_MANAGERS = {"k8s", "openstack", "vmware", "bare_metal"}


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


def task_telecom_oran_smo_register(
    vendor: str = "", releaseVersion: str = "", plmnId: str = "",
    nonRtRicEndpoint: str = "", o1Endpoint: str = "", observedAt: str = "",
    smoId: str = "", o2Endpoint: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"vendor": vendor, "releaseVersion": releaseVersion,
               "plmnId": plmnId, "nonRtRicEndpoint": nonRtRicEndpoint,
               "o1Endpoint": o1Endpoint, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["vendor", "releaseVersion", "plmnId",
                       "nonRtRicEndpoint", "o1Endpoint", "observedAt"])
    s_id = smoId.strip() or _new_id("smo", vendor, plmnId, nonRtRicEndpoint)
    vid = _vid("oranSmo", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "smo_id": s_id, "vendor": vendor, "release_version": releaseVersion,
        "plmn_id": plmnId,
        "non_rt_ric_endpoint": nonRtRicEndpoint,
        "o1_endpoint": o1Endpoint,
        "o2_endpoint": o2Endpoint or None,
        "registered_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_oran_smo", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "smoId": s_id, "status": row["status"]}


def task_telecom_oran_rapp_onboard(
    smoId: str = "", vendor: str = "", name: str = "", version: str = "",
    packageHash: str = "", observedAt: str = "",
    rappId: str = "", useCases: Any = None,
    requiredA1PolicyTypes: Any = None, requiredR1Services: Any = None,
    packageRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"smoId": smoId, "vendor": vendor, "name": name,
               "version": version, "packageHash": packageHash,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["smoId", "vendor", "name", "version", "packageHash", "observedAt"])
    _require_hash_prefix(packageHash, "packageHash")
    _require_vault_ref(packageRef, "packageRef")
    r_id = rappId.strip() or _new_id("rapp", vendor, name, version)
    vid = _vid("oranRapp", r_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "rapp_id": r_id,
        "smo_vid": _vid("oranSmo", smoId),
        "vendor": vendor, "name": name, "version": version,
        "use_cases": _join(useCases),
        "required_a1_policy_types": _join(requiredA1PolicyTypes),
        "required_r1_services": _join(requiredR1Services),
        "package_hash": packageHash,
        "package_ref": packageRef or None,
        "onboarded_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_oran_rapp", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "rappId": r_id, "status": row["status"]}


def task_telecom_oran_xapp_deploy(
    nearRtRicId: str = "", vendor: str = "", name: str = "",
    version: str = "", packageHash: str = "", observedAt: str = "",
    xappId: str = "", useCases: Any = None,
    e2NodeIds: Any = None, supportedRanFunctions: Any = None,
    packageRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"nearRtRicId": nearRtRicId, "vendor": vendor, "name": name,
               "version": version, "packageHash": packageHash,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["nearRtRicId", "vendor", "name", "version",
                       "packageHash", "observedAt"])
    _require_hash_prefix(packageHash, "packageHash")
    _require_vault_ref(packageRef, "packageRef")
    x_id = xappId.strip() or _new_id("xapp", vendor, name, version)
    vid = _vid("oranXapp", x_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "xapp_id": x_id,
        "near_rt_ric_vid": _vid("nfInstance", nearRtRicId),
        "vendor": vendor, "name": name, "version": version,
        "use_cases": _join(useCases),
        "e2_node_vids": _join_vids(e2NodeIds, "ranNode"),
        "supported_ran_functions": _join(supportedRanFunctions),
        "package_hash": packageHash,
        "package_ref": packageRef or None,
        "deployed_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_oran_xapp", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "xappId": x_id, "status": row["status"]}


def task_telecom_oran_a1_policy(
    rappId: str = "", nearRtRicId: str = "", policyTypeId: str = "",
    useCase: str = "", scopeKind: str = "", scopeVid: str = "",
    statementHash: str = "", action: str = "", observedAt: str = "",
    policyInstanceId: str = "", statementRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"rappId": rappId, "nearRtRicId": nearRtRicId,
               "policyTypeId": policyTypeId, "useCase": useCase,
               "scopeKind": scopeKind, "scopeVid": scopeVid,
               "statementHash": statementHash, "action": action,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["rappId", "nearRtRicId", "policyTypeId", "useCase",
                       "scopeKind", "scopeVid", "statementHash", "action",
                       "observedAt"])
    if useCase not in A1_USE_CASES:
        raise ValueError(f"unsupported useCase: {useCase}")
    if scopeKind not in A1_SCOPE_KINDS:
        raise ValueError(f"unsupported scopeKind: {scopeKind}")
    if action not in A1_ACTIONS:
        raise ValueError(f"unsupported action: {action}")
    _require_hash_prefix(statementHash, "statementHash")
    _require_vault_ref(statementRef, "statementRef")
    p_id = policyInstanceId.strip() or _new_id("a1pol", rappId, policyTypeId, scopeVid, observedAt)
    vid = _vid("oranA1Policy", p_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "policy_instance_id": p_id,
        "rapp_vid": _vid("oranRapp", rappId),
        "near_rt_ric_vid": _vid("nfInstance", nearRtRicId),
        "policy_type_id": policyTypeId,
        "use_case": useCase,
        "scope_kind": scopeKind, "scope_vid": scopeVid,
        "statement_hash": statementHash,
        "statement_ref": statementRef or None,
        "action": action,
        "observed_at": observedAt,
        "status": "applied" if action != "delete" else "deleted",
        **_audit(payload),
    }
    _insert("vertex_telecom_oran_a1_policy", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "policyInstanceId": p_id, "status": row["status"]}


def task_telecom_oran_e2_subscribe(
    xappId: str = "", e2NodeId: str = "", ranFunctionId: str = "",
    serviceModel: str = "", eventTriggerKind: str = "", actionKind: str = "",
    observedAt: str = "",
    subscriptionId: str = "", reportingPeriodMs: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"xappId": xappId, "e2NodeId": e2NodeId,
               "ranFunctionId": ranFunctionId, "serviceModel": serviceModel,
               "eventTriggerKind": eventTriggerKind, "actionKind": actionKind,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["xappId", "e2NodeId", "ranFunctionId",
                       "serviceModel", "eventTriggerKind", "actionKind",
                       "observedAt"])
    if serviceModel not in E2_SERVICE_MODELS:
        raise ValueError(f"unsupported serviceModel: {serviceModel}")
    if eventTriggerKind not in E2_TRIGGERS:
        raise ValueError(f"unsupported eventTriggerKind: {eventTriggerKind}")
    if actionKind not in E2_ACTION_KINDS:
        raise ValueError(f"unsupported actionKind: {actionKind}")
    s_id = subscriptionId.strip() or _new_id("e2sub", xappId, e2NodeId, serviceModel, observedAt)
    vid = _vid("oranE2Subscription", s_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "subscription_id": s_id,
        "xapp_vid": _vid("oranXapp", xappId),
        "e2_node_vid": _vid("ranNode", e2NodeId),
        "ran_function_id": ranFunctionId,
        "service_model": serviceModel,
        "event_trigger_kind": eventTriggerKind,
        "action_kind": actionKind,
        "reporting_period_ms": int(reportingPeriodMs) if reportingPeriodMs is not None else None,
        "observed_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_oran_e2_subscription", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "subscriptionId": s_id, "status": row["status"]}


def task_telecom_oran_e2_indication(
    subscriptionId: str = "", sequenceNumber: int = 0,
    indicationType: str = "", headerHash: str = "", messageHash: str = "",
    observedAt: str = "",
    indicationId: str = "", messageSize: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"subscriptionId": subscriptionId,
               "sequenceNumber": sequenceNumber,
               "indicationType": indicationType,
               "headerHash": headerHash, "messageHash": messageHash,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["subscriptionId", "sequenceNumber", "indicationType",
                       "headerHash", "messageHash", "observedAt"])
    if indicationType not in E2_INDICATION_TYPES:
        raise ValueError(f"unsupported indicationType: {indicationType}")
    seq = int(sequenceNumber)
    if seq <= 0:
        raise ValueError("sequenceNumber must be > 0")
    _require_hash_prefix(headerHash, "headerHash")
    _require_hash_prefix(messageHash, "messageHash")
    i_id = indicationId.strip() or _new_id("e2ind", subscriptionId, seq)
    vid = _vid("oranE2Indication", i_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "indication_id": i_id,
        "subscription_vid": _vid("oranE2Subscription", subscriptionId),
        "sequence_number": seq,
        "indication_type": indicationType,
        "header_hash": headerHash,
        "message_hash": messageHash,
        "message_size": int(messageSize) if messageSize is not None else None,
        "observed_at": observedAt,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_oran_e2_indication", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "indicationId": i_id, "status": row["status"]}


def task_telecom_oran_o1_config(
    smoId: str = "", targetKind: str = "", targetVid: str = "",
    interfaceTransport: str = "", operation: str = "",
    configHash: str = "", observedAt: str = "",
    configId: str = "", yangModuleSet: str = "",
    configRef: str = "", configSize: int | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"smoId": smoId, "targetKind": targetKind,
               "targetVid": targetVid, "interfaceTransport": interfaceTransport,
               "operation": operation, "configHash": configHash,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["smoId", "targetKind", "targetVid",
                       "interfaceTransport", "operation", "configHash",
                       "observedAt"])
    if targetKind not in O1_TARGET_KINDS:
        raise ValueError(f"unsupported targetKind: {targetKind}")
    if interfaceTransport not in O1_TRANSPORTS:
        raise ValueError(f"unsupported interfaceTransport: {interfaceTransport}")
    if operation not in O1_OPERATIONS:
        raise ValueError(f"unsupported operation: {operation}")
    _require_hash_prefix(configHash, "configHash")
    _require_vault_ref(configRef, "configRef")
    c_id = configId.strip() or _new_id("o1cfg", smoId, targetVid, observedAt)
    vid = _vid("oranO1Config", c_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "config_id": c_id,
        "smo_vid": _vid("oranSmo", smoId),
        "target_kind": targetKind, "target_vid": targetVid,
        "interface_transport": interfaceTransport,
        "operation": operation,
        "yang_module_set": yangModuleSet or None,
        "config_hash": configHash,
        "config_ref": configRef or None,
        "config_size": int(configSize) if configSize is not None else None,
        "observed_at": observedAt,
        "status": "applied",
        **_audit(payload),
    }
    _insert("vertex_telecom_oran_o1_config", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "configId": c_id, "status": row["status"]}


def task_telecom_oran_o2_provision(
    smoId: str = "", oCloudId: str = "", interfaceKind: str = "",
    resourceKind: str = "", deploymentManager: str = "",
    packageHash: str = "", observedAt: str = "",
    resourceId: str = "", packageRef: str = "", requestedFlavor: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"smoId": smoId, "oCloudId": oCloudId,
               "interfaceKind": interfaceKind, "resourceKind": resourceKind,
               "deploymentManager": deploymentManager,
               "packageHash": packageHash, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["smoId", "oCloudId", "interfaceKind", "resourceKind",
                       "deploymentManager", "packageHash", "observedAt"])
    if interfaceKind not in O2_INTERFACE_KINDS:
        raise ValueError(f"unsupported interfaceKind: {interfaceKind}")
    if resourceKind not in O2_RESOURCE_KINDS:
        raise ValueError(f"unsupported resourceKind: {resourceKind}")
    if deploymentManager not in O2_DEPLOYMENT_MANAGERS:
        raise ValueError(f"unsupported deploymentManager: {deploymentManager}")
    _require_hash_prefix(packageHash, "packageHash")
    _require_vault_ref(packageRef, "packageRef")
    r_id = resourceId.strip() or _new_id("o2res", oCloudId, resourceKind, observedAt)
    vid = _vid("oranO2Resource", r_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "resource_id": r_id,
        "smo_vid": _vid("oranSmo", smoId),
        "o_cloud_id": oCloudId,
        "interface_kind": interfaceKind,
        "resource_kind": resourceKind,
        "deployment_manager": deploymentManager,
        "package_ref": packageRef or None,
        "package_hash": packageHash,
        "requested_flavor": requestedFlavor or None,
        "observed_at": observedAt,
        "status": "provisioned",
        **_audit(payload),
    }
    _insert("vertex_telecom_oran_o2_resource", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "resourceId": r_id, "status": row["status"]}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.oran.smo.register",  single_value=False, timeout_ms=timeout_ms)(task_telecom_oran_smo_register)
    worker.task(task_type="telecom.oran.rapp.onboard",  single_value=False, timeout_ms=timeout_ms)(task_telecom_oran_rapp_onboard)
    worker.task(task_type="telecom.oran.xapp.deploy",   single_value=False, timeout_ms=timeout_ms)(task_telecom_oran_xapp_deploy)
    worker.task(task_type="telecom.oran.a1.policy",     single_value=False, timeout_ms=timeout_ms)(task_telecom_oran_a1_policy)
    worker.task(task_type="telecom.oran.e2.subscribe",  single_value=False, timeout_ms=timeout_ms)(task_telecom_oran_e2_subscribe)
    worker.task(task_type="telecom.oran.e2.indication", single_value=False, timeout_ms=timeout_ms)(task_telecom_oran_e2_indication)
    worker.task(task_type="telecom.oran.o1.config",     single_value=False, timeout_ms=timeout_ms)(task_telecom_oran_o1_config)
    worker.task(task_type="telecom.oran.o2.provision",  single_value=False, timeout_ms=timeout_ms * 2)(task_telecom_oran_o2_provision)
