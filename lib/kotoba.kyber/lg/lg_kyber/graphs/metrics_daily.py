"""kyber metrics_daily — daily KPI snapshot feeding bmc_agent.

Runs daily at 09:00 JST. Collects OSS + Cloud KPIs and writes to
vertex_kyber_metrics_snapshot.

Pipeline: collect_oss → collect_cloud → collect_revenue → write_snapshot → report
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from lg_kyber.db import execute, fetchval

_log = logging.getLogger(__name__)


class MetricsDailyState(TypedDict, total=False):
    run_date: str
    trigger: str
    oss_stars_30d: int
    oss_downloads_30d: int
    cloud_tenants_free: int
    cloud_tenants_paid: int
    cloud_mrr_jpy: int
    cloud_api_calls_24h: int
    leads_new: int
    summary: str


async def collect_oss(state: MetricsDailyState) -> MetricsDailyState:
    today = datetime.now(timezone.utc).date().isoformat()
    stars = 0
    downloads = 0
    try:
        stars = int(
            await fetchval(
                """
                SELECT COUNT(*) FROM vertex_kyber_oss_event
                WHERE event_type = 'star'
                  AND created_at >= NOW() - INTERVAL '30 days'
                """
            ) or 0
        )
        downloads = int(
            await fetchval(
                """
                SELECT COUNT(*) FROM vertex_kyber_oss_event
                WHERE event_type = 'download'
                  AND created_at >= NOW() - INTERVAL '30 days'
                """
            ) or 0
        )
    except Exception as e:
        _log.debug("[kyber.metrics_daily] oss collect failed: %s", e)
    return {**state, "run_date": today, "oss_stars_30d": stars, "oss_downloads_30d": downloads}


async def collect_cloud(state: MetricsDailyState) -> MetricsDailyState:
    tenants_free = 0
    tenants_paid = 0
    api_calls = 0
    try:
        tenants_free = int(
            await fetchval(
                "SELECT COUNT(*) FROM vertex_kyber_tenant WHERE tier = 'free' AND status = 'active'"
            ) or 0
        )
        tenants_paid = int(
            await fetchval(
                "SELECT COUNT(*) FROM vertex_kyber_tenant WHERE tier != 'free' AND status = 'active'"
            ) or 0
        )
        api_calls = int(
            await fetchval(
                """
                SELECT COALESCE(SUM(api_call_count_24h), 0)
                FROM vertex_kyber_tenant
                WHERE status = 'active'
                """
            ) or 0
        )
    except Exception as e:
        _log.debug("[kyber.metrics_daily] cloud collect failed: %s", e)
    return {**state, "cloud_tenants_free": tenants_free, "cloud_tenants_paid": tenants_paid, "cloud_api_calls_24h": api_calls}


async def collect_revenue(state: MetricsDailyState) -> MetricsDailyState:
    mrr = 0
    leads_new = 0
    try:
        mrr = int(
            await fetchval(
                """
                SELECT COALESCE(SUM(qty), 0) FROM vertex_kyber_billing_event
                WHERE metric = 'mrr_jpy'
                  AND ts_ms >= EXTRACT(EPOCH FROM date_trunc('month', NOW())) * 1000
                """
            ) or 0
        )
        leads_new = int(
            await fetchval(
                "SELECT COUNT(*) FROM vertex_kyber_lead WHERE outreach_status = 'new'"
            ) or 0
        )
    except Exception as e:
        _log.debug("[kyber.metrics_daily] revenue collect failed: %s", e)
    return {**state, "cloud_mrr_jpy": mrr, "leads_new": leads_new}


async def write_snapshot(state: MetricsDailyState) -> MetricsDailyState:
    try:
        import json
        snapshot = {
            "oss_stars_30d": state.get("oss_stars_30d", 0),
            "oss_downloads_30d": state.get("oss_downloads_30d", 0),
            "cloud_tenants_free": state.get("cloud_tenants_free", 0),
            "cloud_tenants_paid": state.get("cloud_tenants_paid", 0),
            "cloud_mrr_jpy": state.get("cloud_mrr_jpy", 0),
            "cloud_api_calls_24h": state.get("cloud_api_calls_24h", 0),
            "leads_new": state.get("leads_new", 0),
        }
        await execute(
            """
            INSERT INTO vertex_kyber_metrics_snapshot
              (snapshot_id, run_date, payload_json, created_at)
            VALUES ($1, $2, $3, $4)
            """,
            str(uuid.uuid4()),
            state.get("run_date", datetime.now(timezone.utc).date().isoformat()),
            json.dumps(snapshot),
            datetime.now(timezone.utc),
        )
    except Exception as e:
        _log.warning("[kyber.metrics_daily] write_snapshot failed (table may not exist yet): %s", e)
    return state


async def report(state: MetricsDailyState) -> MetricsDailyState:
    run_date = state.get("run_date", "")
    summary = (
        f"[{run_date}] kyber metrics: oss_stars30d={state.get('oss_stars_30d', 0)} "
        f"tenants={state.get('cloud_tenants_free', 0)}F+{state.get('cloud_tenants_paid', 0)}P "
        f"mrr=¥{state.get('cloud_mrr_jpy', 0):,} "
        f"leads_new={state.get('leads_new', 0)}"
    )
    _log.info("[kyber.metrics_daily] %s", summary)
    return {**state, "summary": summary}


def _build() -> Any:
    sg = StateGraph(MetricsDailyState)
    sg.add_node("collect_oss", collect_oss)
    sg.add_node("collect_cloud", collect_cloud)
    sg.add_node("collect_revenue", collect_revenue)
    sg.add_node("write_snapshot", write_snapshot)
    sg.add_node("report", report)
    sg.add_edge(START, "collect_oss")
    sg.add_edge("collect_oss", "collect_cloud")
    sg.add_edge("collect_cloud", "collect_revenue")
    sg.add_edge("collect_revenue", "write_snapshot")
    sg.add_edge("write_snapshot", "report")
    sg.add_edge("report", END)
    return sg.compile()


GRAPH = _build()
