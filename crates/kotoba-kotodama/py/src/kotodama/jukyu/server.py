"""FastAPI / Granian server for the resident Jukyu agent loop.

Surface:
  POST /runs                  invoke a graph manually
  POST /cron/equilibrium      resident 15-minute global equilibrium loop
  POST /cron/domain-adapter/naphtha
  POST /cron/domain-adapter/crude-oil
  POST /cron/domain-adapter/transport
  POST /cron/outbox-drain     inspect pending signal outbox
  GET  /health                liveness/readiness
  GET  /graphs                graph IDs
"""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from kotodama.jukyu.adapter import normalize_crude_oil, normalize_entity_vessel_transport, normalize_naphtha, normalize_semiconductor
from kotodama.jukyu.graph import build_graph
from kotodama.kotoba_datomic import get_kotoba_client

_GRAPH = build_graph()
GRAPHS: dict[str, Any] = {"jukyu_global_equilibrium_v1": _GRAPH}

app = FastAPI(
    title="lg-jukyu",
    description="Resident LangGraph server for jukyu.etzhayyim.com global supply-demand equilibrium.",
    version="0.1.0",
)


def _enforce_auth(x_api_key: str | None) -> None:
    expected = os.environ.get("LG_JUKYU_API_KEY")
    if not expected:
        return
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="x-api-key mismatch")


@app.get("/health")
@app.get("/ok")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "app": "lg-jukyu",
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
    graph_id = body.get("graph", "jukyu_global_equilibrium_v1")
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
    inp.setdefault("riskThreshold", float(os.environ.get("JUKYU_RISK_THRESHOLD", "0.55")))
    inp.setdefault("maxBalanceRows", int(os.environ.get("JUKYU_MAX_BALANCE_ROWS", "100")))
    inp.setdefault("maxChainRows", int(os.environ.get("JUKYU_MAX_CHAIN_ROWS", "500")))
    inp.setdefault("maxExposureRows", int(os.environ.get("JUKYU_MAX_EXPOSURE_ROWS", "250")))
    return await runs({"graph": "jukyu_global_equilibrium_v1", "input": inp}, x_api_key=x_api_key)


@app.post("/cron/domain-adapter/naphtha")
async def cron_domain_adapter_naphtha(
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> dict[str, Any]:
    _enforce_auth(x_api_key)
    try:
        return normalize_naphtha()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:500])


@app.post("/cron/domain-adapter/crude-oil")
async def cron_domain_adapter_crude_oil(
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> dict[str, Any]:
    _enforce_auth(x_api_key)
    try:
        return normalize_crude_oil()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:500])


@app.post("/cron/domain-adapter/semiconductor")
async def cron_domain_adapter_semiconductor(
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> dict[str, Any]:
    _enforce_auth(x_api_key)
    try:
        return normalize_semiconductor()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:500])


@app.post("/cron/domain-adapter/transport")
async def cron_domain_adapter_transport(
    body: dict[str, Any] | None = None,
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> dict[str, Any]:
    _enforce_auth(x_api_key)
    try:
        return normalize_entity_vessel_transport((body or {}).get("domain"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:500])


@app.post("/cron/outbox-drain")
async def cron_outbox_drain(
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> dict[str, Any]:
    _enforce_auth(x_api_key)
    try:
        # R0: Datalog does not natively support ORDER BY or LIMIT.
        # Fetching all records and applying sorting/limiting in Python.
        query_edn = """
        [:find ?signal_id ?target_company_did ?target_channel ?domain
                ?severity ?risk_score ?confidence ?notification_status
         :where [?e :mv-jukyu-notification-outbox/signal-id ?signal_id]
                [?e :mv-jukyu-notification-outbox/target-company-did ?target_company_did]
                [?e :mv-jukyu-notification-outbox/target-channel ?target_channel]
                [?e :mv-jukyu-notification-outbox/domain ?domain]
                [?e :mv-jukyu-notification-outbox/severity ?severity]
                [?e :mv-jukyu-notification-outbox/risk-score ?risk_score]
                [?e :mv-jukyu-notification-outbox/confidence ?confidence]
                [?e :mv-jukyu-notification-outbox/notification-status ?notification_status]]
        """
        raw_rows = get_kotoba_client().q(query_edn)

        # Sort by risk_score DESC (risk_score is at index 5)
        sorted_rows = sorted(raw_rows, key=lambda x: x[5], reverse=True)
        # Apply limit
        rows = sorted_rows[:250]
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
                "signalId": row[0],
                "targetCompanyDid": row[1],
                "targetChannel": row[2],
                "domain": row[3],
                "severity": row[4],
                "riskScore": row[5],
                "confidence": row[6],
                "status": row[7],
            }
            for row in rows
        ],
    }
