"""
lawfirm.msGraph.* — MS Graph subscription lifecycle for mail reply capture.

Task types:
  lawfirm.msGraph.subscriptionEnsure  Create subscription if absent, return id
  lawfirm.msGraph.subscriptionRenew   PATCH expiration on all known subs (R/PT24H BPMN)

MS Graph mail subscriptions max ~70hr TTL; we extend to 4,200 min on each tick.
Token: app-only (Mail.Read tenant scope) via existing microsoft.etzhayyim.com
identity. Token cache via env MS_GRAPH_APP_TOKEN (refreshed by separate
microsoft.etzhayyim.com cron primitive).

Persists into kotoba Datom log (table vertex_lawfirm_msgraph_subscription) so renewal worker can find
all live subs.

ADR-0036 Hyperdrive direct.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("lawfirm.msgraph")

_FIRM_DID = "did:web:lawfirm.etzhayyim.com"
_RENEW_MINUTES = 4200          # MS Graph max for mail subscriptions
_RENEW_AHEAD_MINUTES = 60 * 24  # renew if expiring within 24h


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def _now_plus_minutes(minutes: int) -> str:
    return (datetime.now(tz=timezone.utc) +
            _dt.timedelta(minutes=int(minutes))).strftime("%Y-%m-%dT%H:%M:%SZ")

def _vid(kind: str) -> str:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.{kind}/{stamp}-{uuid.uuid4().hex[:8]}"


def _ms_token() -> str:
    return os.environ.get("MS_GRAPH_APP_TOKEN", "")

def _ms_post(url: str, body_json: dict, method: str = "POST") -> dict:
    token = _ms_token()
    if not token:
        return {"_dry_run": True}
    body = json.dumps(body_json).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


# ── Task: subscriptionEnsure ─────────────────────────────────────────────────

async def task_lawfirm_msgraph_subscription_ensure(
    user_upn: str = "k.bakshi@etzhayyim.com",
    folder: str = "Inbox",
    notification_url: str = "https://lawfirm.etzhayyim.com/xrpc/com.etzhayyim.apps.lawfirm.mailReplyWebhook",
    client_state: str = "",
) -> dict:
    """Ensure a live MS Graph mail subscription exists for the given UPN."""
    client = get_kotoba_client()
    existing = client.select_first_where(
        "vertex_lawfirm_msgraph_subscription",
        "user_upn",
        user_upn,
        columns=["subscription_id", "expires_at"],
        where={"status": "active"}
    )
    if existing:
        return {
            "ok": True,
            "subscription_id": existing["subscription_id"],
            "expires_at": existing["expires_at"],
            "created": False,
        }

    cs = client_state or os.environ.get("MS_GRAPH_SUB_CLIENT_STATE", "") or uuid.uuid4().hex
    expires_at = _now_plus_minutes(_RENEW_MINUTES)
    body = {
        "changeType":          "created",
        "notificationUrl":     notification_url,
        "resource":            f"users/{user_upn}/mailFolders/{folder}/messages",
        "expirationDateTime":  expires_at,
        "clientState":         cs,
        "latestSupportedTlsVersion": "v1_2",
    }
    resp = _ms_post("https://graph.microsoft.com/v1.0/subscriptions", body)
    sub_id = resp.get("id", "") or f"dry-{uuid.uuid4().hex[:24]}"
    dry = bool(resp.get("_dry_run"))

    client.insert_row(
        "vertex_lawfirm_msgraph_subscription",
        {
            "vertex_id": _vid("msgraphSubscription"),
            "subscription_id": sub_id,
            "user_upn": user_upn,
            "resource": body["resource"],
            "notification_url": notification_url,
            "client_state": cs,
            "expires_at": expires_at,
            "status": "active",
            "last_renewed_at": _now_iso(),
            "created_at": _now_iso(),
            "owner_did": _FIRM_DID,
        },
    )
    LOG.info("MS Graph subscription ensured upn=%s sub=%s dry=%s", user_upn, sub_id, dry)
    return {
        "ok": True,
        "subscription_id": sub_id,
        "expires_at": expires_at,
        "created": True,
        "dry_run": dry,
    }


# ── Task: subscriptionRenew (R/PT24H) ────────────────────────────────────────

async def task_lawfirm_msgraph_subscription_renew() -> dict:
    """PATCH expirationDateTime on all live subs that expire within 24h."""
    client = get_kotoba_client()
    subs = client.select_where(
        "vertex_lawfirm_msgraph_subscription",
        "status",
        "active",
        columns=["vertex_id", "subscription_id", "user_upn", "expires_at"]
    )
    if not subs:
        return {"ok": True, "renewed": 0, "checked": 0}

    threshold_iso = _now_plus_minutes(_RENEW_AHEAD_MINUTES)
    renewed = 0
    errors: list[str] = []

    for s in subs:
        sub_id = s["subscription_id"]
        cur_exp = s.get("expires_at") or ""
        # Renew if expiry is empty OR within 24h window
        if cur_exp and cur_exp > threshold_iso:
            continue
        new_exp = _now_plus_minutes(_RENEW_MINUTES)
        body = {"expirationDateTime": new_exp}
        try:
            resp = _ms_post(
                f"https://graph.microsoft.com/v1.0/subscriptions/{sub_id}",
                body, method="PATCH",
            )
            dry = bool(resp.get("_dry_run"))
            client.insert_row(
                "vertex_lawfirm_msgraph_subscription",
                {
                    "vertex_id": s["vertex_id"],
                    "expires_at": new_exp,
                    "last_renewed_at": _now_iso(),
                },
            )
            renewed += 1
            LOG.info("MS Graph sub renewed id=%s exp=%s dry=%s", sub_id, new_exp, dry)
        except Exception as exc:
            errors.append(f"{sub_id}: {exc}")
            LOG.error("MS Graph renew failed id=%s: %s", sub_id, exc)

    return {
        "ok":      len(errors) == 0,
        "renewed": renewed,
        "checked": len(subs),
        "errors":  errors[:5],
    }


# ── Worker registration ──────────────────────────────────────────────────────

def register(app: Any, timeout_ms: int = 60_000) -> None:
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="lawfirm.msGraph.subscriptionEnsure",
              timeout_ms=timeout_ms, max_jobs_to_activate=2)
    async def _ensure(user_upn: str = "k.bakshi@etzhayyim.com",
                      folder: str = "Inbox",
                      notification_url: str = "https://lawfirm.etzhayyim.com/xrpc/com.etzhayyim.apps.lawfirm.mailReplyWebhook",
                      client_state: str = "") -> dict:
        return await task_lawfirm_msgraph_subscription_ensure(
            user_upn=user_upn, folder=folder,
            notification_url=notification_url, client_state=client_state,
        )

    @app.task(task_type="lawfirm.msGraph.subscriptionRenew",
              timeout_ms=timeout_ms, max_jobs_to_activate=2)
    async def _renew() -> dict:
        return await task_lawfirm_msgraph_subscription_renew()

    LOG.info("Registered tasks: lawfirm.msGraph.{subscriptionEnsure,subscriptionRenew}")
