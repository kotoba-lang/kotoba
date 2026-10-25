"""kyber BMC autonomous strategy agent — daily cron graph.

Runs daily at 09:03 JST. Checks OSS adoption + Cloud pipeline health
and notifies via Teams webhook.

Pipeline: check_pipeline → check_sprint → assess_state → notify → END

Env vars:
  TEAMS_KYBER_WEBHOOK_URL   — Teams incoming webhook (optional)
  KYBER_H1_GITHUB_TARGET    — "true" when GitHub star target reached
  KYBER_H2_CLOUD_BETA       — "true" when Cloud beta launched
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import date, datetime, timezone
from typing import Any, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from lg_kyber.db import execute, fetchval
from . import _llm  # type: ignore[attr-defined]

_log = logging.getLogger(__name__)

TODAY = date.today


class BmcAgentState(TypedDict, total=False):
    run_date: str
    oss_stars_30d: int
    cloud_tenants: int
    cloud_mrr_jpy: int
    pipeline_stuck: bool
    h1_github_target: bool
    h2_cloud_beta: bool
    is_monday: bool
    priority_action: str
    summary: str
    notified: bool


async def check_pipeline(state: BmcAgentState) -> BmcAgentState:
    today_str = TODAY().isoformat()
    oss_stars = 0
    cloud_tenants = 0
    cloud_mrr = 0
    stuck = False
    try:
        oss_stars = int(
            await fetchval(
                """
                SELECT COUNT(*) FROM vertex_kyber_oss_event
                WHERE event_type = 'star'
                  AND created_at >= NOW() - INTERVAL '30 days'
                """
            ) or 0
        )
    except Exception as e:
        _log.debug("[kyber.bmc_agent] oss_stars query failed: %s", e)
    try:
        cloud_tenants = int(
            await fetchval(
                "SELECT COUNT(*) FROM vertex_kyber_tenant WHERE status = 'active'"
            ) or 0
        )
    except Exception as e:
        _log.debug("[kyber.bmc_agent] cloud_tenants query failed: %s", e)
    try:
        cloud_mrr = int(
            await fetchval(
                """
                SELECT COALESCE(SUM(qty), 0) FROM vertex_kyber_billing_event
                WHERE metric = 'mrr_jpy'
                  AND ts_ms >= EXTRACT(EPOCH FROM date_trunc('month', NOW())) * 1000
                """
            ) or 0
        )
    except Exception as e:
        _log.debug("[kyber.bmc_agent] cloud_mrr query failed: %s", e)
    try:
        stuck_count = await fetchval(
            """
            SELECT COUNT(*) FROM vertex_kyber_outbox
            WHERE status = 'queued-no-recipient'
              AND created_at < NOW() - INTERVAL '48 hours'
            """
        )
        stuck = (stuck_count or 0) > 0
    except Exception as e:
        _log.debug("[kyber.bmc_agent] pipeline_stuck query failed: %s", e)

    return {
        **state,
        "run_date": today_str,
        "oss_stars_30d": oss_stars,
        "cloud_tenants": cloud_tenants,
        "cloud_mrr_jpy": cloud_mrr,
        "pipeline_stuck": stuck,
    }


async def check_sprint(state: BmcAgentState) -> BmcAgentState:
    today = TODAY()
    return {
        **state,
        "h1_github_target": os.environ.get("KYBER_H1_GITHUB_TARGET", "").lower() == "true",
        "h2_cloud_beta": os.environ.get("KYBER_H2_CLOUD_BETA", "").lower() == "true",
        "is_monday": today.weekday() == 0,
    }


async def assess_state(state: BmcAgentState) -> BmcAgentState:
    stuck = state.get("pipeline_stuck", False)
    stars = state.get("oss_stars_30d", 0)
    tenants = state.get("cloud_tenants", 0)
    mrr = state.get("cloud_mrr_jpy", 0)

    if stuck:
        priority = "URGENT: outbox stuck >48h — approve or reject items"
    elif not state.get("h1_github_target"):
        priority = "H1: GitHub star target未達 — OSS promotion / HN Show HN 検討"
    elif not state.get("h2_cloud_beta"):
        priority = "H2: Cloud beta 未公開 — Stripe billing tables 実装を優先"
    elif state.get("is_monday"):
        priority = f"週次: Cloud MRR ¥{mrr:,} / {tenants}テナント確認 (ARR目標 ¥3M)"
    else:
        priority = f"異常なし — kyber growth actors 自律運転中 (stars 30d={stars}, tenants={tenants})"

    llm_note = ""
    try:
        prompt = (
            f"kyber BMC daily. oss_stars_30d={stars} cloud_tenants={tenants} mrr_jpy={mrr}. "
            f"priority={priority}. "
            "One concise strategic observation ≤80 chars (Japanese OK). "
            'JSON: {"note": "..."}'
        )
        parsed, source = _llm.call_llm_json(prompt, max_tokens=100)
        if parsed and source == "llm":
            llm_note = f" | {str(parsed.get('note', ''))[:80]}"
    except Exception:
        pass

    run_date = state.get("run_date", TODAY().isoformat())
    summary = (
        f"[{run_date}] kyber: stars30d={stars} tenants={tenants} mrr=¥{mrr:,} "
        f"| H1:{'✅' if state.get('h1_github_target') else '⏳'} "
        f"H2:{'✅' if state.get('h2_cloud_beta') else '⏳'} "
        f"| {priority}{llm_note}"
    )

    return {**state, "priority_action": priority, "summary": summary}


async def notify(state: BmcAgentState) -> BmcAgentState:
    summary = state.get("summary", "")
    notified = False

    webhook_url = os.environ.get("TEAMS_KYBER_WEBHOOK_URL", "")
    if webhook_url:
        try:
            payload = {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {"type": "TextBlock", "text": "kyber BMC Daily", "weight": "Bolder", "size": "Medium"},
                            {"type": "TextBlock", "text": summary, "wrap": True},
                        ],
                    },
                }],
            }
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(webhook_url, json=payload)
                r.raise_for_status()
            notified = True
            _log.info("[kyber.bmc_agent] Teams notification sent")
        except Exception as e:
            _log.warning("[kyber.bmc_agent] Teams webhook failed: %s", e)

    if not notified:
        run_date = state.get("run_date", TODAY().isoformat())
        try:
            await execute(
                """
                INSERT INTO vertex_kyber_outbox
                  (vertex_id, org_did, kind, subject, body_text,
                   recipient_email, status, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                str(uuid.uuid4()),
                "did:web:kyber.etzhayyim.com",
                "bmc-daily-report",
                f"kyber BMC Daily {run_date}",
                summary,
                "jun@etzhayyim.group",
                "queued-no-recipient",
                datetime.now(timezone.utc),
            )
            notified = True
        except Exception as e:
            _log.warning("[kyber.bmc_agent] outbox insert failed: %s", e)

    _log.info("[kyber.bmc_agent] %s", summary)
    return {**state, "notified": notified}


def _build() -> Any:
    sg = StateGraph(BmcAgentState)
    sg.add_node("check_pipeline", check_pipeline)
    sg.add_node("check_sprint", check_sprint)
    sg.add_node("assess_state", assess_state)
    sg.add_node("notify", notify)
    sg.add_edge(START, "check_pipeline")
    sg.add_edge("check_pipeline", "check_sprint")
    sg.add_edge("check_sprint", "assess_state")
    sg.add_edge("assess_state", "notify")
    sg.add_edge("notify", END)
    return sg.compile()


GRAPH = _build()
