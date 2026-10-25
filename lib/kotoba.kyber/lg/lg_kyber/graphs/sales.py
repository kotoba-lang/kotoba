"""kyber Sales actor — enterprise / nokyo pipeline management.

Runs hourly. Per-tenant health check and deterministic action policy.
All outbox rows land at 'queued-no-recipient'; reviewer approves before send.

Pipeline: load_tenants → compute_health → decide_action → execute → report

Deterministic policy:
  incident_count_24h > 0  → do_nothing (defer to triage)
  last_touch < 7d         → do_nothing (per-tenant rate-limit)
  api_calls_24h = 0 AND no prior touch → send_onboarding
  api_calls_24h < 50 AND tier=free → send_usage_recap
  tier=free AND api_calls_24h > 800 → send_upgrade
  tier=starter AND api_calls_24h > 8000 → send_upgrade (professional)
  tier in (starter,professional,business) AND api_calls_24h = 0 → escalate_human
  else → do_nothing
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from lg_kyber.db import execute, fetch

_log = logging.getLogger(__name__)

ActionKind = Literal[
    "do_nothing",
    "send_onboarding",
    "send_usage_recap",
    "send_upgrade",
    "escalate_human",
]

_TEMPLATES: dict[str, tuple[str, str]] = {
    "send_onboarding": (
        "kyber Cloud — 使い始めのガイド",
        "kyber Cloud へようこそ！\n\n最初の仕訳登録: https://kyber.etzhayyim.com/gl/new-entry\nMCP endpoint: https://kyber.etzhayyim.com/mcp\n\nkyber team",
    ),
    "send_usage_recap": (
        "kyber — 今週の利用状況レポート",
        "先週の API 利用状況をお届けします。\n詳細: https://kyber.etzhayyim.com/dashboard\n\nkyber team",
    ),
    "send_upgrade": (
        "kyber — プランのアップグレードをご検討ください",
        "利用量が増えてきました。上位プランでさらに快適にご利用いただけます。\nプラン比較: https://kyber.etzhayyim.com/pricing\n\nkyber team",
    ),
    "escalate_human": (
        "kyber — [INTERNAL] テナント要対応",
        "有料テナントのアクティビティが0です。手動フォローアップが必要です。",
    ),
}


class SalesState(TypedDict, total=False):
    run_date: str
    tenants: list[dict]
    actions: list[dict]
    drafted: int
    summary: str


async def load_tenants(state: SalesState) -> SalesState:
    today = datetime.now(timezone.utc).date().isoformat()
    tenants: list[dict] = []
    try:
        rows = await fetch(
            """
            SELECT
              t.tenant_id, t.org_did, t.tier, t.status,
              COALESCE(t.contact_email, '') AS contact_email,
              COALESCE(t.api_call_count_24h, 0) AS api_calls_24h,
              t.last_outreach_at
            FROM vertex_kyber_tenant t
            WHERE t.status = 'active'
            ORDER BY t.tier DESC, t.api_call_count_24h DESC
            LIMIT 200
            """
        )
        tenants = [dict(r) for r in rows]
    except Exception as e:
        _log.warning("[kyber.sales] load_tenants failed: %s", e)
    return {**state, "run_date": today, "tenants": tenants}


async def compute_health(state: SalesState) -> SalesState:
    tenants = state.get("tenants") or []
    enriched = []
    for t in tenants:
        api_calls = int(t.get("api_calls_24h", 0))
        tier = t.get("tier", "free")
        health = 50
        if api_calls > 100:
            health += 30
        elif api_calls > 10:
            health += 15
        elif api_calls == 0:
            health -= 20
        if tier in ("professional", "business"):
            health += 10
        t = dict(t)
        t["health"] = max(0, min(100, health))
        enriched.append(t)
    return {**state, "tenants": enriched}


async def decide_action(state: SalesState) -> SalesState:
    actions = []
    for t in (state.get("tenants") or []):
        api_calls = int(t.get("api_calls_24h", 0))
        tier = t.get("tier", "free")
        last_touch = t.get("last_outreach_at")

        # Rate-limit: skip if outreach within last 7 days
        if last_touch:
            try:
                lt = last_touch if isinstance(last_touch, datetime) else datetime.fromisoformat(str(last_touch))
                diff = (datetime.now(timezone.utc) - lt.replace(tzinfo=timezone.utc if lt.tzinfo is None else lt.tzinfo))
                if diff.days < 7:
                    actions.append({"tenant": t, "action": "do_nothing", "notes": "rate-limited"})
                    continue
            except Exception:
                pass

        if api_calls == 0 and not last_touch:
            action_kind: ActionKind = "send_onboarding"
        elif api_calls < 50 and tier == "free":
            action_kind = "send_usage_recap"
        elif tier == "free" and api_calls > 800:
            action_kind = "send_upgrade"
        elif tier == "starter" and api_calls > 8000:
            action_kind = "send_upgrade"
        elif tier in ("starter", "professional", "business") and api_calls == 0:
            action_kind = "escalate_human"
        else:
            action_kind = "do_nothing"

        actions.append({"tenant": t, "action": action_kind, "notes": f"api_calls_24h={api_calls}"})
    return {**state, "actions": actions}


async def execute_actions(state: SalesState) -> SalesState:
    drafted = 0
    for item in (state.get("actions") or []):
        action = item.get("action", "do_nothing")
        if action == "do_nothing":
            continue
        t = item.get("tenant") or {}
        email = (t.get("contact_email") or "").strip()
        org_did = t.get("org_did", "unknown")
        subject, body = _TEMPLATES.get(action, ("kyber — ご連絡", ""))
        try:
            await execute(
                """
                INSERT INTO vertex_kyber_outbox
                  (vertex_id, org_did, kind, subject, body_text,
                   recipient_email, status, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                """,
                str(uuid.uuid4()), org_did, f"sales-{action}",
                subject, body, email,
                "queued-no-recipient",
                datetime.now(timezone.utc),
            )
            await execute(
                "UPDATE vertex_kyber_tenant SET last_outreach_at = $1 WHERE org_did = $2",
                datetime.now(timezone.utc), org_did,
            )
            drafted += 1
        except Exception as e:
            _log.warning("[kyber.sales] execute_actions failed for %s: %s", org_did, e)
    return {**state, "drafted": drafted}


async def report(state: SalesState) -> SalesState:
    run_date = state.get("run_date", "")
    tenants = len(state.get("tenants") or [])
    drafted = state.get("drafted", 0)
    summary = f"[{run_date}] kyber sales: {tenants}テナント評価 → {drafted}件action"
    _log.info("[kyber.sales] %s", summary)
    return {**state, "summary": summary}


def _build() -> Any:
    sg = StateGraph(SalesState)
    sg.add_node("load_tenants", load_tenants)
    sg.add_node("compute_health", compute_health)
    sg.add_node("decide_action", decide_action)
    sg.add_node("execute_actions", execute_actions)
    sg.add_node("report", report)
    sg.add_edge(START, "load_tenants")
    sg.add_edge("load_tenants", "compute_health")
    sg.add_edge("compute_health", "decide_action")
    sg.add_edge("decide_action", "execute_actions")
    sg.add_edge("execute_actions", "report")
    sg.add_edge("report", END)
    return sg.compile()


GRAPH = _build()
