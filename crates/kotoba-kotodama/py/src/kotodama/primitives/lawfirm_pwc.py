"""
lawfirm.pwc.* — LangServer handlers for the pwcClearance.bpmn workflow.

Task types:
  lawfirm.pwc.persistRequest   INSERT clearance request row, return SLA deadline
  lawfirm.pwc.notifyCEO        Notify CEO via Microsoft Teams (sendDraft)
  lawfirm.pwc.applyDecision    Persist CEO clearance decision + matter unlock/decline

CEO decision D4 (2026-05-08): per-matter PwC India compliance escalation,
NOT auto-screen via hash list.

ADR-0036 Hyperdrive direct.
"""

from __future__ import annotations

import datetime
from datetime import timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


# ── Task: lawfirm.pwc.persistRequest ─────────────────────────────────────────

async def task_lawfirm_pwc_persist_request(
    matter_uri: str = "",
    client_name: str = "",
    matter_summary: str = "",
    requested_by_did: str = "",
    pwc_contact: str = "",
    sla_hours: int = 72,
) -> dict:
    if not matter_uri or not client_name:
        return {"ok": False, "error": "matter_uri + client_name required"}

    clearance_uri = _vid("pwcClearance")
    sla_deadline = (_dt.datetime.now(tz=_dt.UTC) +
                    _dt.timedelta(hours=int(sla_hours))).strftime("%Y-%m-%d %H:%M:%S")

    _execute(
        "INSERT INTO vertex_lawfirm_pwc_clearance "
        "(vertex_id, matter_uri, client_name, matter_summary, requested_at, "
        " requested_by_did, pwc_contact, clearance_status, sla_deadline, "
        " escalated, created_at, owner_did) "
        "VALUES (:vid, :muri, :cname, :msum, :req_at, :req_by, :pwcc, "
        " 'pending', :sla, false, :now, :owner)",
        {
            "vid":    clearance_uri,
            "muri":   matter_uri,
            "cname":  client_name[:200],
            "msum":   matter_summary[:1000],
            "req_at": _now_iso(),
            "req_by": requested_by_did or _FIRM_DID,
            "pwcc":   pwc_contact[:200],
            "sla":    sla_deadline,
            "now":    _now_iso(),
            "owner":  _FIRM_DID,
        },
    )

    return {
        "ok":             True,
        "clearance_uri":  clearance_uri,
        "sla_deadline":   sla_deadline,
    }


# ── Task: lawfirm.pwc.notifyCEO ──────────────────────────────────────────────

async def task_lawfirm_pwc_notify_ceo(
    clearance_uri: str = "",
    client_name: str = "",
    matter_summary: str = "",
    sla_deadline: str = "",
) -> dict:
    """Notify CEO via Microsoft Teams channel email (Mail.Send app-only)."""
    subject = f"[PwC clearance] {client_name} — SLA {sla_deadline}"
    body_md = (
        f"### PwC India Compliance Clearance Required\n\n"
        f"- **Client**: {client_name}\n"
        f"- **Matter summary**: {matter_summary or '(not provided)'}\n"
        f"- **Clearance URI**: `{clearance_uri}`\n"
        f"- **SLA deadline**: **{sla_deadline}**\n\n"
        f"PwC India compliance に formal email を起案いただき、回答を `lawfirm.pwc.applyDecision` "
        f"XRPC で記録ください (no_conflict / conflict / need_more_info)。\n\n"
        f"このメッセージは pwcClearance.bpmn から自動送信されています。"
    )

    # Best-effort: invoke microsoft.etzhayyim.com sendDraft via dispatcher.
    # If the dispatcher is unreachable, we still mark as "notified-fallback"
    # and rely on the SLA-deadline cronjob to nag the CEO.
    notified_via = "log_only"
    try:
        import urllib.request
        body = json.dumps({
            "to": [_TEAMS_CHANNEL_EMAIL],
            "subject": subject,
            "body_md": body_md,
            "send_now": True,
        }).encode()
        url = os.environ.get(
            "BPMN_DISPATCHER_INTERNAL_URL",
            "http://bpmn-dispatcher.mitama-udf.svc.cluster.local:8080",
        ) + "/xrpc/com.etzhayyim.apps.microsoft.sendMail"
        secret = os.environ.get("BPMN_DISPATCHER_INTERNAL_SECRET", "")
        headers = {"Content-Type": "application/json"}
        if secret:
            headers["x-internal-trust"] = secret
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            _ = resp.read()
        notified_via = "microsoft_teams_email"
    except Exception as exc:
        LOG.info("Teams notify fallback (log only) — %s", exc)

    LOG.info(
        "PwC clearance notify CEO=%s clearance=%s via=%s sla=%s",
        _CEO_DID, clearance_uri, notified_via, sla_deadline,
    )
    return {"ok": True, "notified_via": notified_via}


# ── Task: lawfirm.pwc.applyDecision ──────────────────────────────────────────

_DECISION_TO_STATUS = {
    "no_conflict":   "cleared",
    "conflict":      "declined",
    "need_more_info": "pending_more_info",
}


async def task_lawfirm_pwc_apply_decision(
    clearance_uri: str = "",
    clearance_decision: str = "",
    pwc_response_text: str = "",
    matter_uri: str = "",
) -> dict:
    if not clearance_uri or not clearance_decision:
        return {"ok": False, "error": "clearance_uri + clearance_decision required"}

    new_status = _DECISION_TO_STATUS.get(clearance_decision, "pending")

    _execute(
        "UPDATE vertex_lawfirm_pwc_clearance "
        "SET pwc_response = :resp, pwc_response_text = :rtext, "
        "    responded_at = :now, clearance_status = :status "
        "WHERE vertex_id = :vid",
        {
            "resp":   clearance_decision,
            "rtext":  pwc_response_text[:2000],
            "now":    _now_iso(),
            "status": new_status,
            "vid":    clearance_uri,
        },
    )

    # If a matter is bound, propagate status change
    if matter_uri:
        if new_status == "cleared":
            _execute(
                "UPDATE vertex_lawfirm_matter SET status = 'active' "
                "WHERE vertex_id = :muri AND status = 'pending_pwc'",
                {"muri": matter_uri},
            )
        elif new_status == "declined":
            _execute(
                "UPDATE vertex_lawfirm_matter SET status = 'declined_conflict' "
                "WHERE vertex_id = :muri",
                {"muri": matter_uri},
            )

    LOG.info(
        "PwC clearance applied uri=%s decision=%s status=%s matter=%s",
        clearance_uri, clearance_decision, new_status, matter_uri,
    )
    return {
        "ok":               True,
        "clearance_status": new_status,
        "decision":         clearance_decision,
    }


# ── Worker registration ──────────────────────────────────────────────────────

def register(app: Any, timeout_ms: int = 60_000) -> None:
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="lawfirm.pwc.persistRequest",
              timeout_ms=timeout_ms, max_jobs_to_activate=4)
    async def _persist(matter_uri: str = "", client_name: str = "",
                       matter_summary: str = "", requested_by_did: str = "",
                       pwc_contact: str = "", sla_hours: int = 72) -> dict:
        return await task_lawfirm_pwc_persist_request(
            matter_uri=matter_uri, client_name=client_name,
            matter_summary=matter_summary, requested_by_did=requested_by_did,
            pwc_contact=pwc_contact, sla_hours=sla_hours,
        )

    @app.task(task_type="lawfirm.pwc.notifyCEO",
              timeout_ms=timeout_ms, max_jobs_to_activate=4)
    async def _notify(clearance_uri: str = "", client_name: str = "",
                      matter_summary: str = "", sla_deadline: str = "") -> dict:
        return await task_lawfirm_pwc_notify_ceo(
            clearance_uri=clearance_uri, client_name=client_name,
            matter_summary=matter_summary, sla_deadline=sla_deadline,
        )

    @app.task(task_type="lawfirm.pwc.applyDecision",
              timeout_ms=timeout_ms, max_jobs_to_activate=4)
    async def _apply(clearance_uri: str = "", clearance_decision: str = "",
                     pwc_response_text: str = "", matter_uri: str = "") -> dict:
        return await task_lawfirm_pwc_apply_decision(
            clearance_uri=clearance_uri,
            clearance_decision=clearance_decision,
            pwc_response_text=pwc_response_text,
            matter_uri=matter_uri,
        )

    LOG.info("Registered tasks: lawfirm.pwc.{persistRequest,notifyCEO,applyDecision}")
