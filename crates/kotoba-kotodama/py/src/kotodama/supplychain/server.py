"""FastAPI / Granian server for the resident supplychain agent loop.

Surface:
  POST /runs                           invoke a graph manually
  POST /cron/equilibrium               resident 15-minute Pregel loop
  POST /cron/domain-adapter/cleaning-robot  normalize robotics/automotive tables
  POST /cron/outbox-drain              inspect pending signal outbox
  GET  /health                         liveness/readiness
  GET  /graphs                         graph IDs
"""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from kotodama.supplychain.adapter import normalize_cleaning_robot
from kotodama.supplychain.graph import build_graph
from kotodama.kotoba_datomic import get_kotoba_client

_GRAPH = build_graph()
GRAPHS: dict[str, Any] = {"supplychain_cleaning_robot_v1": _GRAPH}

app = FastAPI(
    title="lg-supplychain",
    description="Resident LangGraph server for supplychain.etzhayyim.com cleaning-robot material Pregel.",
    version="0.1.0",
)


def _enforce_auth(x_api_key: str | None) -> None:
    expected = os.environ.get("LG_SUPPLYCHAIN_API_KEY")
    if not expected:
        return
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="x-api-key mismatch")


@app.get("/health")
@app.get("/ok")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "app": "lg-supplychain",
        "ts": int(time.time() * 1000),
        "graphs": list(GRAPHS.keys()),
    }


@app.get("/graphs")
def list_graphs() -> dict[str, Any]:
    return {"graphs": list(GRAPHS.keys())}


@app.post("/runs")
async def runs(
    body: dict[str, Any],
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> dict[str, Any]:
    _enforce_auth(x_api_key)
    graph_id = body.get("graph", "supplychain_cleaning_robot_v1")
    if graph_id not in GRAPHS:
        raise HTTPException(status_code=404, detail=f"unknown graph: {graph_id}")
    inp = dict(body.get("input") or {})
    config = dict(body.get("config") or {})
    t0 = time.time()
    try:
        result = await GRAPHS[graph_id].ainvoke(inp, config=config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:500])
    return {
        "ok": bool(result.get("ok", True)),
        "graph": graph_id,
        "duration_ms": int((time.time() - t0) * 1000),
        "result": result,
    }


@app.post("/cron/equilibrium")
async def cron_equilibrium(
    body: dict[str, Any] | None = None,
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> dict[str, Any]:
    _enforce_auth(x_api_key)
    inp = dict(body or {})
    inp.setdefault("domain", os.environ.get("SUPPLYCHAIN_DOMAIN", "cleaning_robot"))
    inp.setdefault("riskThreshold", float(os.environ.get("SUPPLYCHAIN_RISK_THRESHOLD", "0.55")))
    inp.setdefault("maxBalanceRows", int(os.environ.get("SUPPLYCHAIN_MAX_BALANCE_ROWS", "100")))
    inp.setdefault("maxChainRows", int(os.environ.get("SUPPLYCHAIN_MAX_CHAIN_ROWS", "500")))
    inp.setdefault("maxExposureRows", int(os.environ.get("SUPPLYCHAIN_MAX_EXPOSURE_ROWS", "250")))
    return await runs({"graph": "supplychain_cleaning_robot_v1", "input": inp}, x_api_key=x_api_key)


@app.post("/cron/domain-adapter/cleaning-robot")
async def cron_domain_adapter_cleaning_robot(
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> dict[str, Any]:
    _enforce_auth(x_api_key)
    try:
        return normalize_cleaning_robot()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:500])


@app.post("/cron/outbox-drain")
async def cron_outbox_drain(
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> dict[str, Any]:
    _enforce_auth(x_api_key)
    domain = os.environ.get("SUPPLYCHAIN_DOMAIN", "cleaning_robot")
    try:
        # R0: Order by risk_score DESC and LIMIT 100 in Python as kotoba_datomic select_where does not support ORDER BY.
        client = get_kotoba_client()
        all_rows = client.select_where(
            "mv_jukyu_notification_outbox",
            "domain",
            domain,
            columns=[
                "signal_id", "target_company_did", "target_channel", "domain",
                "severity", "risk_score", "confidence", "notification_status"
            ],
            limit=2000 # Fetch more rows to allow in-Python sorting
        )
        # Sort by risk_score descending and take the top 100
        rows = sorted(all_rows, key=lambda x: x.get("risk_score", 0.0), reverse=True)[:100]
    except Exception as exc:
        return {
            "ok": False,
            "dbReady": False,
            "count": 0,
            "signals": [],
            "error": str(exc)[:500],
        }
    return {
        "ok": True,
        "count": len(rows),
        "signals": [
            {
                "signalId": row["signal_id"],
                "targetCompanyDid": row["target_company_did"],
                "targetChannel": row["target_channel"],
                "domain": row["domain"],
                "severity": row["severity"],
                "riskScore": row["risk_score"],
                "confidence": row["confidence"],
                "status": row["notification_status"],
            }
            for row in rows
        ],
    }
