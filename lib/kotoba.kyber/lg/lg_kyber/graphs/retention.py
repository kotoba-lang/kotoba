"""kyber Retention actor — churn signal detection + win-back for paid tenants.

Runs daily at 11:00 JST. Detects paid tenants with zero API activity
in the last 14 days and sends win-back messages.

Pipeline: find_churning → enqueue_winback → report
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from lg_kyber.db import execute, fetch

_log = logging.getLogger(__name__)

_WINBACK_SUBJECT = "kyber — 最近ご利用がありませんが、お困りではないでしょうか？"
_WINBACK_BODY = """\
こんにちは！

kyber をご利用いただきありがとうございます。
最近 API のアクティビティが確認できていないため、ご連絡しました。

もしお困りの点がありましたら、いつでもお気軽にご相談ください:
  → https://kyber.etzhayyim.com/support

◆ 最近のアップデート
  - Murakumo LLM による自動仕訳提案
  - APQC PCF 13 L1 全業界対応
  - AT Protocol データポータビリティ (いつでも自社サーバーに移行可能)

引き続きよろしくお願いします。

kyber team
"""


class RetentionState(TypedDict, total=False):
    run_date: str
    churning: list[dict]
    sent: int
    summary: str


async def find_churning(state: RetentionState) -> RetentionState:
    today = datetime.now(timezone.utc).date().isoformat()
    churning: list[dict] = []
    try:
        rows = await fetch(
            """
            SELECT t.tenant_id, t.org_did,
                   COALESCE(t.contact_email, '') AS contact_email,
                   t.tier
            FROM vertex_kyber_tenant t
            WHERE t.tier IN ('starter', 'professional', 'business')
              AND t.status = 'active'
              AND COALESCE(t.last_api_call_at, t.created_at) < NOW() - INTERVAL '14 days'
            LIMIT 50
            """
        )
        churning = [dict(r) for r in rows]
    except Exception as e:
        _log.warning("[kyber.retention] find_churning query failed: %s", e)

    _log.info("[kyber.retention] churning candidates: %d", len(churning))
    return {**state, "run_date": today, "churning": churning}


async def enqueue_winback(state: RetentionState) -> RetentionState:
    sent = 0
    for tenant in (state.get("churning") or []):
        email = (tenant.get("contact_email") or "").strip()
        org_did = tenant.get("org_did", "unknown")
        try:
            existing = await fetch(
                "SELECT 1 FROM vertex_kyber_outbox WHERE org_did = $1 AND kind = 'retention-winback' AND created_at > NOW() - INTERVAL '30 days' LIMIT 1",
                org_did,
            )
            if existing:
                continue
        except Exception:
            pass
        try:
            await execute(
                """
                INSERT INTO vertex_kyber_outbox
                  (vertex_id, org_did, kind, subject, body_text,
                   recipient_email, status, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                """,
                str(uuid.uuid4()), org_did, "retention-winback",
                _WINBACK_SUBJECT, _WINBACK_BODY, email,
                "queued-no-recipient" if not email else "queued",
                datetime.now(timezone.utc),
            )
            sent += 1
        except Exception as e:
            _log.warning("[kyber.retention] winback insert failed for %s: %s", org_did, e)
    return {**state, "sent": sent}


async def report(state: RetentionState) -> RetentionState:
    run_date = state.get("run_date", "")
    sent = state.get("sent", 0)
    summary = f"[{run_date}] kyber retention: win-back={sent}件送信"
    _log.info("[kyber.retention] %s", summary)
    return {**state, "summary": summary}


def _build() -> Any:
    sg = StateGraph(RetentionState)
    sg.add_node("find_churning", find_churning)
    sg.add_node("enqueue_winback", enqueue_winback)
    sg.add_node("report", report)
    sg.add_edge(START, "find_churning")
    sg.add_edge("find_churning", "enqueue_winback")
    sg.add_edge("enqueue_winback", "report")
    sg.add_edge("report", END)
    return sg.compile()


GRAPH = _build()
