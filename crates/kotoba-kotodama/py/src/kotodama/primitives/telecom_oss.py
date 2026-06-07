"""telecom Phase 7 primitives — OSS-NMS Operations.

Eight BPMN service tasks bound to the telecom actor:

  - telecom.oss.alarm.raise       (3GPP TS 32.111 / ITU-T X.733 fault mgmt)
  - telecom.oss.alarm.correlate
  - telecom.oss.alarm.suppress
  - telecom.oss.alarm.clear       (computes MTTR from raised_at)
  - telecom.oss.change.submit     (ITIL change request)
  - telecom.oss.change.approve    (CAB decision)
  - telecom.oss.config.snapshot   (drift detection vs baseline)
  - telecom.oss.capacity.forecast (breach prediction vs limit)

Pattern conventions:
  - `clearAlarm`, `suppressAlarm`, `approveChangeRequest` mutate existing
    rows via UPDATE (single source of truth per alarm/change).
  - `snapshotConfiguration` computes drift by comparing config_hash
    against the baseline snapshot's hash (no-baseline → drift=false).
  - `forecastCapacity` sets `breach_predicted = forecast_value >
    capacity_limit`.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


TELECOM_DID = "did:web:telecom.etzhayyim.com"
ACTOR_TAG = "sys.worker.telecom.oss"

SOURCE_KINDS = {"cellSite", "ranNode", "nfInstance", "networkAsset", "service", "transport"}
ALARM_TYPES = {"communications", "quality_of_service", "processing_error", "equipment", "environmental", "integrity_violation"}
SEVERITIES = {"info", "warning", "minor", "major", "critical"}
CORRELATION_KINDS = {"root_cause", "topology", "temporal", "rule_engine", "ml_clustering"}
SUPPRESSION_REASONS = {"maintenance", "known_issue", "duplicate", "test", "operator_override"}
CLEAR_KINDS = {"operator", "auto", "expired", "duplicate", "false_positive"}
CHANGE_KINDS = {"normal", "standard", "emergency"}
RISK_LEVELS = {"low", "medium", "high", "very_high"}
CHANGE_SCOPE_KINDS = {"cellSite", "ranNode", "nfInstance", "networkAsset", "service", "transport", "global"}
APPROVAL_DECISIONS = {"approved", "rejected", "deferred", "withdrawn"}
APPROVER_ROLES = {"change_manager", "cab_chair", "service_owner", "security_officer", "regulatory"}
CONFIG_SCOPE_KINDS = {"cellSite", "ranNode", "nfInstance", "networkAsset", "transport"}
CAPACITY_SCOPE_KINDS = {"cellSite", "ranNode", "nfInstance", "service", "transport", "spectrum"}
MODEL_KINDS = {"linear", "arima", "prophet", "lstm", "manual"}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _new_id(prefix: str, *parts: Any) -> str:
    if parts:
        digest = hashlib.sha256("|".join(str(p) for p in parts).hexdigest())[:24]
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


# ─── Task implementations ───────────────────────────────────────────────


def task_telecom_oss_alarm_raise(
    sourceKind: str = "", sourceVid: str = "", alarmType: str = "",
    severity: str = "", raisedAt: str = "",
    alarmId: str = "", perceivedSeverity: str = "",
    probableCause: str = "", alarmText: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"sourceKind": sourceKind, "sourceVid": sourceVid,
               "alarmType": alarmType, "severity": severity,
               "raisedAt": raisedAt, "callerDid": callerDid}
    _require(payload, ["sourceKind", "sourceVid", "alarmType", "severity", "raisedAt"])
    if sourceKind not in SOURCE_KINDS:
        raise ValueError(f"unsupported sourceKind: {sourceKind}")
    if alarmType not in ALARM_TYPES:
        raise ValueError(f"unsupported alarmType: {alarmType}")
    if severity not in SEVERITIES:
        raise ValueError(f"unsupported severity: {severity}")
    if perceivedSeverity and perceivedSeverity not in SEVERITIES:
        raise ValueError(f"unsupported perceivedSeverity: {perceivedSeverity}")
    a_id = alarmId.strip() or _new_id("alm", sourceVid, alarmType, raisedAt)
    vid = _vid("alarm", a_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "alarm_id": a_id,
        "source_kind": sourceKind, "source_vid": sourceVid,
        "alarm_type": alarmType, "severity": severity,
        "perceived_severity": perceivedSeverity or severity,
        "probable_cause": probableCause or None,
        "alarm_text": alarmText or None,
        "raised_at": raisedAt,
        "cleared_at": None, "mttr_seconds": None,
        "clear_kind": None, "cleared_by": None, "resolution_ref": None,
        "suppress_until": None, "suppression_reason": None,
        "suppressed_by": None, "window_vid": None,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_alarm", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "alarmId": a_id, "status": row["status"]}


def task_telecom_oss_alarm_correlate(
    parentAlarmId: str = "", childAlarmIds: Any = None,
    correlationKind: str = "", observedAt: str = "",
    correlationId: str = "", ruleRef: str = "",
    confidence: float | None = None,
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"parentAlarmId": parentAlarmId, "childAlarmIds": childAlarmIds,
               "correlationKind": correlationKind, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["parentAlarmId", "childAlarmIds", "correlationKind", "observedAt"])
    if correlationKind not in CORRELATION_KINDS:
        raise ValueError(f"unsupported correlationKind: {correlationKind}")
    children = list(childAlarmIds) if isinstance(childAlarmIds, (list, tuple)) else []
    if not children:
        raise ValueError("childAlarmIds must be a non-empty list")
    c_id = correlationId.strip() or _new_id("corr", parentAlarmId, observedAt)
    vid = _vid("alarmCorrelation", c_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "correlation_id": c_id,
        "parent_alarm_vid": _vid("alarm", parentAlarmId),
        "child_count": len(children),
        "correlation_kind": correlationKind,
        "rule_ref": ruleRef or None,
        "confidence": float(confidence) if confidence is not None else None,
        "observed_at": observedAt,
        "status": "active",
        **_audit(payload),
    }
    _insert("vertex_telecom_alarm_correlation", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "correlationId": c_id,
            "childCount": len(children), "status": row["status"]}


def task_telecom_oss_alarm_suppress(
    alarmId: str = "", suppressionReason: str = "",
    suppressUntil: str = "", suppressedBy: str = "", observedAt: str = "",
    windowVid: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"alarmId": alarmId, "suppressionReason": suppressionReason,
               "suppressUntil": suppressUntil, "suppressedBy": suppressedBy,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["alarmId", "suppressionReason", "suppressUntil",
                       "suppressedBy", "observedAt"])
    if suppressionReason not in SUPPRESSION_REASONS:
        raise ValueError(f"unsupported suppressionReason: {suppressionReason}")
    vid = _vid("alarm", alarmId)

    status = "suppressed"
    if not dryRun:
        client = get_kotoba_client()
        existing_alarm = client.select_first_where(
            "vertex_telecom_alarm", "vertex_id", vid,
        )
        if existing_alarm:
            existing_alarm["suppress_until"] = suppressUntil
            existing_alarm["suppression_reason"] = suppressionReason
            existing_alarm["suppressed_by"] = suppressedBy
            existing_alarm["window_vid"] = windowVid or None
            existing_alarm["status"] = status
            _insert("vertex_telecom_alarm", existing_alarm, dry_run=dryRun)
        else:
            raise ValueError(f"Alarm with vertex_id {vid} not found for suppression.")
    return {"ok": True, "vertexId": vid, "alarmId": alarmId, "status": status}


def task_telecom_oss_alarm_clear(
    alarmId: str = "", clearKind: str = "",
    clearedBy: str = "", clearedAt: str = "",
    resolutionRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"alarmId": alarmId, "clearKind": clearKind,
               "clearedBy": clearedBy, "clearedAt": clearedAt,
               "callerDid": callerDid}
    _require(payload, ["alarmId", "clearKind", "clearedBy", "clearedAt"])
    if clearKind not in CLEAR_KINDS:
        raise ValueError(f"unsupported clearKind: {clearKind}")
    vid = _vid("alarm", alarmId)

    mttr = None
    status = "cleared"
    if not dryRun:
        client = get_kotoba_client()
        existing_alarm = client.select_first_where(
            "vertex_telecom_alarm", "vertex_id", vid,
        )
        if existing_alarm:
            raised_at_str = existing_alarm.get("raised_at")
            if raised_at_str:
                raised_at_dt = datetime.fromisoformat(raised_at_str).astimezone(UTC)
                cleared_at_dt = datetime.fromisoformat(clearedAt).astimezone(UTC)
                mttr_seconds = (cleared_at_dt - raised_at_dt).total_seconds()
                mttr = float(mttr_seconds) if mttr_seconds is not None else None

            existing_alarm["cleared_at"] = clearedAt
            existing_alarm["clear_kind"] = clearKind
            existing_alarm["cleared_by"] = clearedBy
            existing_alarm["resolution_ref"] = resolutionRef or None
            existing_alarm["mttr_seconds"] = mttr
            existing_alarm["status"] = status
            _insert("vertex_telecom_alarm", existing_alarm, dry_run=dryRun)
        else:
            raise ValueError(f"Alarm with vertex_id {vid} not found for clearing.")

    return {"ok": True, "vertexId": vid, "alarmId": alarmId,
            "mttrSeconds": mttr, "status": status}


def task_telecom_oss_change_submit(
    requesterId: str = "", changeKind: str = "", riskLevel: str = "",
    scopeKind: str = "", scopeVid: str = "", summary: str = "",
    plannedStart: str = "", plannedEnd: str = "",
    changeId: str = "", planRef: str = "", rollbackPlanRef: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"requesterId": requesterId, "changeKind": changeKind,
               "riskLevel": riskLevel, "scopeKind": scopeKind,
               "scopeVid": scopeVid, "summary": summary,
               "plannedStart": plannedStart, "plannedEnd": plannedEnd,
               "callerDid": callerDid}
    _require(payload, ["requesterId", "changeKind", "riskLevel", "scopeKind",
                       "scopeVid", "summary", "plannedStart", "plannedEnd"])
    if changeKind not in CHANGE_KINDS:
        raise ValueError(f"unsupported changeKind: {changeKind}")
    if riskLevel not in RISK_LEVELS:
        raise ValueError(f"unsupported riskLevel: {riskLevel}")
    if scopeKind not in CHANGE_SCOPE_KINDS:
        raise ValueError(f"unsupported scopeKind: {scopeKind}")
    c_id = changeId.strip() or _new_id("chg", requesterId, scopeVid, plannedStart)
    vid = _vid("changeRequest", c_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "change_id": c_id,
        "requester_id": requesterId,
        "change_kind": changeKind, "risk_level": riskLevel,
        "scope_kind": scopeKind, "scope_vid": scopeVid,
        "summary": summary,
        "plan_ref": planRef or None,
        "planned_start": plannedStart, "planned_end": plannedEnd,
        "scheduled_start": None, "scheduled_end": None,
        "rollback_plan_ref": rollbackPlanRef or None,
        "submitted_at": _now_iso(),
        "decision": None, "decision_reason": None,
        "approver_id": None, "approver_role": None, "decided_at": None,
        "status": "submitted",
        **_audit(payload),
    }
    _insert("vertex_telecom_change_request", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "changeId": c_id, "status": row["status"]}


def task_telecom_oss_change_approve(
    changeId: str = "", decision: str = "",
    approverId: str = "", approverRole: str = "", observedAt: str = "",
    approvalId: str = "", decisionReason: str = "",
    scheduledStart: str = "", scheduledEnd: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"changeId": changeId, "decision": decision,
               "approverId": approverId, "approverRole": approverRole,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["changeId", "decision", "approverId", "approverRole", "observedAt"])
    if decision not in APPROVAL_DECISIONS:
        raise ValueError(f"unsupported decision: {decision}")
    if approverRole not in APPROVER_ROLES:
        raise ValueError(f"unsupported approverRole: {approverRole}")
    a_id = approvalId.strip() or _new_id("appr", changeId, approverId, observedAt)
    vid = _vid("changeApproval", a_id)
    change_vid = _vid("changeRequest", changeId)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "approval_id": a_id,
        "change_vid": change_vid,
        "decision": decision,
        "approver_id": approverId, "approver_role": approverRole,
        "decision_reason": decisionReason or None,
        "observed_at": observedAt,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_change_approval", row, dry_run=dryRun)

    change_status = decision
    if not dryRun:
        client = get_kotoba_client()
        existing_change_request = client.select_first_where(
            "vertex_telecom_change_request", "vertex_id", change_vid,
        )
        if existing_change_request:
            existing_change_request["decision"] = decision
            existing_change_request["decision_reason"] = decisionReason or None
            existing_change_request["approver_id"] = approverId
            existing_change_request["approver_role"] = approverRole
            existing_change_request["decided_at"] = observedAt
            existing_change_request["scheduled_start"] = scheduledStart or existing_change_request.get("scheduled_start")
            existing_change_request["scheduled_end"] = scheduledEnd or existing_change_request.get("scheduled_end")
            existing_change_request["status"] = decision
            _insert("vertex_telecom_change_request", existing_change_request, dry_run=dryRun)
            change_status = existing_change_request["status"]
        else:
            raise ValueError(f"Change request with vertex_id {change_vid} not found for approval.")

    return {"ok": True, "vertexId": vid, "approvalId": a_id,
            "changeStatus": change_status, "status": row["status"]}


def task_telecom_oss_config_snapshot(
    scopeKind: str = "", scopeVid: str = "", sourceSystem: str = "",
    configHash: str = "", observedAt: str = "",
    snapshotId: str = "", configRef: str = "",
    configSize: int | None = None, baselineSnapshotId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"scopeKind": scopeKind, "scopeVid": scopeVid,
               "sourceSystem": sourceSystem, "configHash": configHash,
               "observedAt": observedAt, "callerDid": callerDid}
    _require(payload, ["scopeKind", "scopeVid", "sourceSystem", "configHash", "observedAt"])
    if scopeKind not in CONFIG_SCOPE_KINDS:
        raise ValueError(f"unsupported scopeKind: {scopeKind}")
    if not (configHash.startswith("sha256:") or configHash.startswith("sha384:") or configHash.startswith("sha512:")):
        raise ValueError("configHash must be prefixed with sha256:|sha384:|sha512:")
    if configRef and not configRef.startswith("vault://"):
        raise ValueError("configRef must be a vault:// pointer")
    s_id = snapshotId.strip() or _new_id("cfg", scopeVid, configHash[:16], observedAt)
    vid = _vid("configSnapshot", s_id)
    baseline_vid = _vid("configSnapshot", baselineSnapshotId) if baselineSnapshotId else None
    drift = False
    if baseline_vid and not dryRun:
        client = get_kotoba_client()
        baseline_snapshot = client.select_first_where(
            "vertex_telecom_config_snapshot", "vertex_id", baseline_vid,
            columns=["config_hash"]
        )
        if baseline_snapshot and baseline_snapshot.get("config_hash") != configHash:
            drift = True
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "snapshot_id": s_id,
        "scope_kind": scopeKind, "scope_vid": scopeVid,
        "source_system": sourceSystem,
        "config_hash": configHash,
        "config_ref": configRef or None,
        "config_size": int(configSize) if configSize is not None else None,
        "baseline_snapshot_vid": baseline_vid,
        "drift": drift,
        "observed_at": observedAt,
        "status": "captured",
        **_audit(payload),
    }
    _insert("vertex_telecom_config_snapshot", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "snapshotId": s_id,
            "drift": drift, "status": row["status"]}


def task_telecom_oss_capacity_forecast(
    scopeKind: str = "", scopeVid: str = "", metric: str = "",
    currentValue: float = 0.0, forecastValue: float = 0.0,
    forecastHorizonDays: int = 0, capacityLimit: float = 0.0,
    modelKind: str = "", observedAt: str = "",
    forecastId: str = "",
    callerDid: str = "", dryRun: bool = False,
) -> dict[str, Any]:
    payload = {"scopeKind": scopeKind, "scopeVid": scopeVid, "metric": metric,
               "modelKind": modelKind, "observedAt": observedAt,
               "callerDid": callerDid}
    _require(payload, ["scopeKind", "scopeVid", "metric", "modelKind", "observedAt"])
    if scopeKind not in CAPACITY_SCOPE_KINDS:
        raise ValueError(f"unsupported scopeKind: {scopeKind}")
    if modelKind not in MODEL_KINDS:
        raise ValueError(f"unsupported modelKind: {modelKind}")
    horizon = int(forecastHorizonDays)
    if horizon <= 0:
        raise ValueError("forecastHorizonDays must be > 0")
    cur_v = float(currentValue)
    fc_v = float(forecastValue)
    cap_v = float(capacityLimit)
    if cap_v <= 0:
        raise ValueError("capacityLimit must be > 0")
    breach = fc_v > cap_v
    f_id = forecastId.strip() or _new_id("fc", scopeVid, metric, observedAt, horizon)
    vid = _vid("capacityForecast", f_id)
    row = {
        "vertex_id": vid, "owner_did": _caller(payload),
        "forecast_id": f_id,
        "scope_kind": scopeKind, "scope_vid": scopeVid,
        "metric": metric,
        "current_value": cur_v, "forecast_value": fc_v,
        "forecast_horizon_days": horizon,
        "capacity_limit": cap_v,
        "breach_predicted": breach,
        "model_kind": modelKind,
        "observed_at": observedAt,
        "status": "recorded",
        **_audit(payload),
    }
    _insert("vertex_telecom_capacity_forecast", row, dry_run=dryRun)
    return {"ok": True, "vertexId": vid, "forecastId": f_id,
            "breachPredicted": breach, "status": row["status"]}


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    worker.task(task_type="telecom.oss.alarm.raise",       single_value=False, timeout_ms=timeout_ms)(task_telecom_oss_alarm_raise)
    worker.task(task_type="telecom.oss.alarm.correlate",   single_value=False, timeout_ms=timeout_ms)(task_telecom_oss_alarm_correlate)
    worker.task(task_type="telecom.oss.alarm.suppress",    single_value=False, timeout_ms=timeout_ms)(task_telecom_oss_alarm_suppress)
    worker.task(task_type="telecom.oss.alarm.clear",       single_value=False, timeout_ms=timeout_ms)(task_telecom_oss_alarm_clear)
    worker.task(task_type="telecom.oss.change.submit",     single_value=False, timeout_ms=timeout_ms)(task_telecom_oss_change_submit)
    worker.task(task_type="telecom.oss.change.approve",    single_value=False, timeout_ms=timeout_ms)(task_telecom_oss_change_approve)
    worker.task(task_type="telecom.oss.config.snapshot",   single_value=False, timeout_ms=timeout_ms)(task_telecom_oss_config_snapshot)
    worker.task(task_type="telecom.oss.capacity.forecast", single_value=False, timeout_ms=timeout_ms)(task_telecom_oss_capacity_forecast)
