"""Minimal OSS FastAPI server for lg-kyber.

Surface:
  POST /runs                  → invoke {graph} synchronously
  GET  /health  /ok           → liveness
  GET  /graphs                → list graph IDs

Auth: optional LG_KYBER_API_KEY env enforces x-api-key on /runs.
Cron path (x-cron=1) is allowed anonymously behind cloudflared tunnel.

Graphs + cron schedule (all JST):
  metrics_daily          09:00  daily
  bmc_agent              09:03  daily
  bmc_iteration          16:00  daily
  activation             08:30  daily
  conversion             10:15  daily
  retention              11:00  daily
  lead_discovery         */6h
  marketing              */6h
  sales                  :15 hourly
  business_operating_react  06:00 daily
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Header, HTTPException

from lg_kyber.db import close_pool, get_pool
from lg_kyber.graphs.health import GRAPH as HEALTH_GRAPH
from lg_kyber.graphs.bmc_iteration import GRAPH as BMC_ITERATION_GRAPH
from lg_kyber.graphs.bmc_agent import GRAPH as BMC_AGENT_GRAPH
from lg_kyber.graphs.lead_discovery import GRAPH as LEAD_DISCOVERY_GRAPH
from lg_kyber.graphs.activation import GRAPH as ACTIVATION_GRAPH
from lg_kyber.graphs.conversion import GRAPH as CONVERSION_GRAPH
from lg_kyber.graphs.retention import GRAPH as RETENTION_GRAPH
from lg_kyber.graphs.marketing import GRAPH as MARKETING_GRAPH
from lg_kyber.graphs.sales import GRAPH as SALES_GRAPH
from lg_kyber.graphs.metrics_daily import GRAPH as METRICS_DAILY_GRAPH
from lg_kyber.graphs.business_operating import GRAPH as BUSINESS_OPERATING_GRAPH
from lg_kyber.graphs.business_operating_react import GRAPH as BUSINESS_OPERATING_REACT_GRAPH

_log = logging.getLogger(__name__)

GRAPHS: dict[str, Any] = {
    "health": HEALTH_GRAPH,
    "bmc_iteration": BMC_ITERATION_GRAPH,
    "bmc_agent": BMC_AGENT_GRAPH,
    # Phase 2 — Autonomous Growth Engine (business_operator actor set)
    "lead_discovery": LEAD_DISCOVERY_GRAPH,
    "activation": ACTIVATION_GRAPH,
    "conversion": CONVERSION_GRAPH,
    "retention": RETENTION_GRAPH,
    "marketing": MARKETING_GRAPH,
    "sales": SALES_GRAPH,
    "metrics_daily": METRICS_DAILY_GRAPH,
    "business_operating": BUSINESS_OPERATING_GRAPH,
    "business_operating_react": BUSINESS_OPERATING_REACT_GRAPH,
}

_scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")

app = FastAPI(
    title="lg-kyber",
    description="LangGraph Server: kyber BMC + Phase 2 Autonomous Growth Engine (business_operator).",
    version="0.0.1",
)


@app.on_event("startup")
async def _startup() -> None:
    try:
        await get_pool()
    except Exception as e:
        _log.warning("[lg-kyber] pool pre-warm failed: %s", e)

    async def _run_metrics_daily() -> None:
        try:
            result = await METRICS_DAILY_GRAPH.ainvoke({"trigger": "cron"})
            _log.info("[kyber.metrics_daily] cron done: %s", result.get("summary", "")[:120])
        except Exception as exc:
            _log.exception("[kyber.metrics_daily] cron failed: %s", exc)

    async def _run_bmc_agent() -> None:
        try:
            result = await BMC_AGENT_GRAPH.ainvoke({"trigger": "cron"})
            _log.info("[kyber.bmc_agent] cron done: %s", result.get("summary", "")[:120])
        except Exception as exc:
            _log.exception("[kyber.bmc_agent] cron failed: %s", exc)

    async def _run_bmc_iteration() -> None:
        try:
            result = await BMC_ITERATION_GRAPH.ainvoke({"trigger": "cron"})
            _log.info("[kyber.bmc_iteration] cron done: %s", result.get("notes", "")[:120])
        except Exception as exc:
            _log.exception("[kyber.bmc_iteration] cron failed: %s", exc)

    async def _run_lead_discovery() -> None:
        try:
            result = await LEAD_DISCOVERY_GRAPH.ainvoke({"trigger": "cron"})
            _log.info("[kyber.lead_discovery] cron done: %s", result.get("summary", "")[:120])
        except Exception as exc:
            _log.exception("[kyber.lead_discovery] cron failed: %s", exc)

    async def _run_activation() -> None:
        try:
            result = await ACTIVATION_GRAPH.ainvoke({"trigger": "cron"})
            _log.info("[kyber.activation] cron done: %s", result.get("summary", "")[:120])
        except Exception as exc:
            _log.exception("[kyber.activation] cron failed: %s", exc)

    async def _run_conversion() -> None:
        try:
            result = await CONVERSION_GRAPH.ainvoke({"trigger": "cron"})
            _log.info("[kyber.conversion] cron done: %s", result.get("summary", "")[:120])
        except Exception as exc:
            _log.exception("[kyber.conversion] cron failed: %s", exc)

    async def _run_retention() -> None:
        try:
            result = await RETENTION_GRAPH.ainvoke({"trigger": "cron"})
            _log.info("[kyber.retention] cron done: %s", result.get("summary", "")[:120])
        except Exception as exc:
            _log.exception("[kyber.retention] cron failed: %s", exc)

    async def _run_marketing() -> None:
        try:
            result = await MARKETING_GRAPH.ainvoke({"trigger": "cron"})
            _log.info("[kyber.marketing] cron done: %s", result.get("summary", "")[:120])
        except Exception as exc:
            _log.exception("[kyber.marketing] cron failed: %s", exc)

    async def _run_sales() -> None:
        try:
            result = await SALES_GRAPH.ainvoke({"trigger": "cron"})
            _log.info("[kyber.sales] cron done: %s", result.get("summary", "")[:120])
        except Exception as exc:
            _log.exception("[kyber.sales] cron failed: %s", exc)

    async def _run_business_operating_react() -> None:
        try:
            result = await BUSINESS_OPERATING_REACT_GRAPH.ainvoke({"product_id": "kyber"})
            report = result.get("report") or {}
            _log.info("[kyber.bo_react] cron done: %s", str(report.get("final_observation", ""))[:120])
        except Exception as exc:
            _log.exception("[kyber.bo_react] cron failed: %s", exc)

    _scheduler.add_job(_run_metrics_daily, "cron", hour=9, minute=0)
    _scheduler.add_job(_run_bmc_agent, "cron", hour=9, minute=3)
    _scheduler.add_job(_run_bmc_iteration, "cron", hour=16, minute=0)
    _scheduler.add_job(_run_activation, "cron", hour=8, minute=30)
    _scheduler.add_job(_run_conversion, "cron", hour=10, minute=15)
    _scheduler.add_job(_run_retention, "cron", hour=11, minute=0)
    _scheduler.add_job(_run_lead_discovery, "cron", hour="0,6,12,18", minute=0)
    _scheduler.add_job(_run_marketing, "cron", hour="0,6,12,18", minute=5)
    _scheduler.add_job(_run_sales, "cron", minute=15)
    _scheduler.add_job(_run_business_operating_react, "cron", hour=6, minute=0)
    _scheduler.start()
    _log.info(
        "[lg-kyber] scheduler started: metrics_daily 09:00, bmc_agent 09:03, bmc_iteration 16:00, "
        "activation 08:30, conversion 10:15, retention 11:00, lead_discovery+marketing */6h, "
        "sales :15 hourly, bo_react 06:00 JST"
    )


@app.on_event("shutdown")
async def _shutdown() -> None:
    _scheduler.shutdown(wait=False)
    await close_pool()


def _enforce_auth(x_api_key: str | None, *, exempt: bool = False) -> None:
    if exempt:
        return
    expected = os.environ.get("LG_KYBER_API_KEY")
    if not expected:
        return
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="x-api-key mismatch")


@app.get("/health")
@app.get("/ok")
def _health() -> dict[str, Any]:
    return {
        "ok": True,
        "app": "lg-kyber",
        "ts": int(time.time() * 1000),
        "graphs": list(GRAPHS.keys()),
    }


@app.get("/graphs")
def _list_graphs() -> dict[str, Any]:
    return {"graphs": list(GRAPHS.keys())}


@app.post("/runs")
async def _runs(
    body: dict[str, Any],
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
    x_cron: str | None = Header(default=None, alias="x-cron"),
) -> dict[str, Any]:
    _enforce_auth(x_api_key, exempt=(x_cron == "1"))
    graph_id = body.get("graph") or body.get("assistant_id")
    if graph_id not in GRAPHS:
        raise HTTPException(status_code=404, detail=f"unknown graph: {graph_id}")
    inp = body.get("input", {})
    config = body.get("config", {})
    t0 = time.time()
    try:
        result = await GRAPHS[graph_id].ainvoke(inp, config=config)
    except Exception as e:
        _log.exception("[lg-kyber][runs] graph=%s failed", graph_id)
        raise HTTPException(status_code=500, detail=str(e)[:300])
    return {
        "ok": True,
        "graph": graph_id,
        "duration_ms": int((time.time() - t0) * 1000),
        "result": result,
    }
