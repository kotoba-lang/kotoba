"""FastAPI surface for kotodama Python worker pods.

This module gives Kubernetes and in-cluster dispatchers a stable HTTP surface
without moving public XRPC/MCP ownership out of the CF Worker / dispatcher
layer.

Run:
    granian --interface asgi --host 0.0.0.0 --port 8081 kotodama.worker_api:app
    python -m kotodama.worker_api
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import os
import sys
import time
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


try:
    from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
except ImportError:  # pragma: no cover - local minimal env fallback
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    Gauge = None  # type: ignore[assignment]
    generate_latest = None  # type: ignore[assignment]

_STARTED_AT = time.time()
_COMPONENT = os.environ.get("WORKER_API_COMPONENT", "kotodama-worker")
_RUNTIME_KIND = os.environ.get("WORKER_API_RUNTIME_KIND", "k8s-langserver")
_RW_URL_SET = bool(os.environ.get("RW_URL"))

_MAPS_DASHBOARD_LABELS = {
    "places": "Place",
    "routes": "Route",
    "buildings": "Building",
    "sensors": "Sensor",
    "roads": "Road",
    "railways": "Railway",
    "airports": "Airport",
    "ports": "Port",
    "stations": "Station",
    "spots": "Spot",
    "rivers": "River",
    "lakes": "Lake",
    "mountains": "Mountain",
    "infraNetworks": "InfraNetwork",
    "infraIncidents": "InfraIncident",
    "simulations": "Simulation",
    "spatialEvents": "SpatialEvent",
    "displayLayers": "DisplayLayer",
    "visionResults": "VisionResult",
    "satelliteScenes": "SatelliteScene",
    "collectionJobs": "CollectionJob",
}

_WORLD_MONITOR_SOURCE_FAMILIES = [
    {
        "id": "conflict-events",
        "name": "Conflict / incident events",
        "worldMonitorAnalog": "ACLED + UCDP",
        "status": "partial",
        "backingLayer": "vertex_spatial:SpatialEvent",
    },
    {
        "id": "military-adsb",
        "name": "Military / ADS-B air tracks",
        "worldMonitorAnalog": "ADS-B Exchange",
        "status": "partial",
        "backingLayer": "vertex_aircraft_state",
    },
    {
        "id": "maritime-ais",
        "name": "Maritime AIS / dark vessel watch",
        "worldMonitorAnalog": "AIS + dark vessel analytics",
        "status": "planned",
        "backingLayer": "aismarine query facade",
    },
    {
        "id": "satellite-imagery",
        "name": "Satellite scenes and analysis",
        "worldMonitorAnalog": "Satellite imagery layers",
        "status": "partial",
        "backingLayer": "SatelliteScene",
    },
    {
        "id": "market-signals",
        "name": "Market, commodity, crypto signals",
        "worldMonitorAnalog": "Markets overlay",
        "status": "partial",
        "backingLayer": "vertex_market_demand_signal",
    },
    {
        "id": "ai-briefs",
        "name": "AI situation briefs",
        "worldMonitorAnalog": "AI briefs",
        "status": "scaffolded",
        "backingLayer": "dashboard-derived brief",
    },
]

if Gauge is not None:
    WORKER_UP = Gauge(
        "kotodama_worker_api_up",
        "Whether the kotodama worker API process is running.",
        ["component", "runtime_kind"],
    )
    WORKER_UP.labels(component=_COMPONENT, runtime_kind=_RUNTIME_KIND).set(1)

app = FastAPI(
    title="kotodama worker api",
    version="1",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class InvokeRequest(BaseModel):
    """LangServer task invocation body.

    `name` is an MCP tool NSID such as `com.etzhayyim.apps.shinka.tick`.
    `arguments` is passed to the registered async task function.
    """

    name: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class McpEnvelopeRequest(BaseModel):
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    id: str | int | None = None
    jsonrpc: str | None = None


def _base_status() -> dict[str, Any]:
    now = time.time()
    return {
        "ok": True,
        "component": _COMPONENT,
        "runtimeKind": _RUNTIME_KIND,
        "uptimeSec": int(now - _STARTED_AT),
        "pid": os.getpid(),
        "rwUrlConfigured": _RW_URL_SET,
    }


def _safe_int(raw: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(min_value, min(value, max_value))


async def _request_payload(request: Request) -> dict[str, Any]:
    if request.method == "GET":
        return dict(request.query_params)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return {}
    return body if isinstance(body, dict) else {}


def _row_dict(columns: tuple[str, ...], row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return {col: row.get(col) for col in columns}
    return {col: row[idx] if idx < len(row) else None for idx, col in enumerate(columns)}


def _maps_count_label(label: str) -> int:
    if True:
        client = get_kotoba_client()
        try:
            _res = client.q(
                "SELECT cnt FROM mv_vertex_spatial_count WHERE label = %s LIMIT 1",
                (label,),
            )
            row = (_res[0] if _res else None)
            return int(row[0] if row else 0)
        except Exception:  # noqa: BLE001
            _res = client.q("SELECT COUNT(*) FROM vertex_spatial WHERE label = %s", (label,))
            row = (_res[0] if _res else None)
            return int(row[0] if row else 0)


def _maps_recent_spatial_events(limit: int = 8) -> list[dict[str, Any]]:
    sql = f"""
    SELECT
      vertex_id, label, name, description,
      category AS event_type,
      status AS severity,
      lat, lng,
      COALESCE(source, source_did, actor_did) AS source,
      CAST(created_date AS varchar) AS created_at
    FROM vertex_spatial
    WHERE label = 'SpatialEvent'
    ORDER BY _seq DESC
    LIMIT {int(limit)}
    """
    cols = (
        "vertex_id",
        "label",
        "name",
        "description",
        "event_type",
        "severity",
        "lat",
        "lng",
        "source",
        "created_at",
    )
    if True:
        client = get_kotoba_client()
        _res = client.q(sql)
        return [_row_dict(cols, row) for row in (_res or [])]


def _maps_market_signal_summary(limit: int = 5) -> dict[str, Any]:
    rows_sql = f"""
    SELECT vertex_id, lane, signal_kind, magnitude, observed_at, created_at, actor_id
    FROM vertex_market_demand_signal
    ORDER BY created_at DESC
    LIMIT {int(limit)}
    """
    summary_sql = """
    SELECT lane, COUNT(*) AS count, COALESCE(SUM(magnitude), 0) AS magnitude
    FROM vertex_market_demand_signal
    GROUP BY lane
    """
    cols = ("vertex_id", "lane", "signal_kind", "magnitude", "observed_at", "created_at", "actor_id")
    if True:
        client = get_kotoba_client()
        _res = client.q("SELECT COUNT(*) FROM vertex_market_demand_signal")
        total_row = (_res[0] if _res else None)
        total = int(total_row[0] if total_row else 0)
        _res = client.q(summary_sql)
        lanes = [
            {"lane": str(row[0] or ""), "count": int(row[1] or 0), "magnitude": float(row[2] or 0)}
            for row in (_res or [])
        ]
        _res = client.q(rows_sql)
        signals = [_row_dict(cols, row) for row in (_res or [])]
    return {"count": total, "lanes": lanes, "signals": signals}


def _maps_list_live_aircraft(payload: dict[str, Any]) -> dict[str, Any]:
    max_age = _safe_int(payload.get("maxAgeSec"), 90, 30, 600)
    limit = _safe_int(payload.get("limit"), 200, 1, 2000)
    cutoff_ms = int(time.time() * 1000) - max_age * 1000
    clauses = [
        "on_ground = false",
        "ts_ms >= %s",
        "lat IS NOT NULL",
        "lon IS NOT NULL",
    ]
    params: list[Any] = [cutoff_ms]
    for key, col, op in (
        ("minLat", "lat", ">="),
        ("maxLat", "lat", "<="),
        ("minLon", "lon", ">="),
        ("maxLon", "lon", "<="),
    ):
        if payload.get(key) is not None:
            clauses.append(f"{col} {op} %s")
            params.append(float(payload[key]))
    if payload.get("country"):
        clauses.append("origin_country = %s")
        params.append(str(payload["country"]))
    sql = f"""
    SELECT
      icao24, callsign, lat, lon, baro_altitude_m, velocity_ms,
      heading_deg, vertical_rate_ms, origin_country, source, ts_ms
    FROM vertex_aircraft_state
    WHERE {' AND '.join(clauses)}
    ORDER BY ts_ms DESC
    LIMIT {limit}
    """
    cols = (
        "icao24",
        "callsign",
        "lat",
        "lon",
        "baroAltitudeM",
        "velocityMs",
        "headingDeg",
        "verticalRateMs",
        "originCountry",
        "source",
        "tsMs",
    )
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, tuple(params))
        aircraft = [_row_dict(cols, row) for row in (_res or [])]
    return {"aircraft": aircraft, "count": len(aircraft), "asOfMs": int(time.time() * 1000), "source": "pod-langserver"}


def _maps_list_live_satellites(payload: dict[str, Any]) -> dict[str, Any]:
    limit = _safe_int(payload.get("limit"), 100, 1, 1000)
    now_ms = int(time.time() * 1000)
    clauses = ["aos_ms <= %s", "los_ms >= %s"]
    params: list[Any] = [now_ms, now_ms]
    if payload.get("observerH3"):
        clauses.append("observer_h3 = %s")
        params.append(str(payload["observerH3"]))
    sql = f"""
    SELECT
      norad_id, observer_h3, aos_ms, los_ms, max_elevation_deg,
      peak_azimuth_deg, visible_at_night, magnitude
    FROM vertex_satellite_pass
    WHERE {' AND '.join(clauses)}
    ORDER BY max_elevation_deg DESC
    LIMIT {limit}
    """
    cols = (
        "noradId",
        "observerH3",
        "aosMs",
        "losMs",
        "maxElevationDeg",
        "peakAzimuthDeg",
        "visibleAtNight",
        "magnitude",
    )
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, tuple(params))
        satellites = [_row_dict(cols, row) for row in (_res or [])]
    return {"satellites": satellites, "count": len(satellites), "asOfMs": now_ms, "source": "pod-langserver"}


def _maps_dashboard() -> dict[str, Any]:
    counts = {name: _maps_count_label(label) for name, label in _MAPS_DASHBOARD_LABELS.items()}
    market = _maps_market_signal_summary()
    counts["marketSignals"] = int(market.get("count") or 0)
    live_aircraft = _maps_list_live_aircraft({"limit": 12})
    live_satellites = _maps_list_live_satellites({"limit": 8})
    aircraft_count = int(live_aircraft.get("count") or 0)
    satellite_count = int(live_satellites.get("count") or 0)
    spatial_events = int(counts["spatialEvents"])
    infra_incidents = int(counts["infraIncidents"])
    collection_jobs = int(counts["collectionJobs"])
    market_signals = int(counts["marketSignals"])
    market_magnitude = sum(float(row.get("magnitude") or 0) for row in market.get("lanes", []))
    risk_score = min(
        100,
        round(
            min(spatial_events, 250) * 0.12
            + min(infra_incidents, 50) * 0.8
            + min(aircraft_count, 200) * 0.05
            + min(collection_jobs, 100) * 0.08
            + min(market_magnitude, 100) * 0.04
        ),
    )
    risk_level = "high" if risk_score >= 70 else "elevated" if risk_score >= 40 else "watch" if risk_score >= 18 else "low"
    layers = [
        {"id": "live-aircraft", "name": "Live Aircraft", "category": "mobility", "enabled": True, "count": aircraft_count, "color": "#10b981", "description": "ADS-B aircraft positions"},
        {"id": "live-satellites", "name": "Live Satellites", "category": "space", "enabled": True, "count": satellite_count, "color": "#ec4899", "description": "SGP4 satellite overlay"},
        {"id": "spatial-events", "name": "Spatial Events", "category": "intel", "enabled": True, "count": spatial_events, "color": "#f97316", "description": "Seismic, sensor, post, and imported events"},
        {"id": "market-signals", "name": "Market Signals", "category": "markets", "enabled": True, "count": market_signals, "color": "#0ea5e9", "description": "Demand, crypto, payment-rail, and commodity pressure signals"},
    ]
    panels = [
        {"id": "risk", "title": "Spatial Risk", "value": risk_score, "status": risk_level, "items": [{"label": "events", "value": spatial_events}, {"label": "infra", "value": infra_incidents}, {"label": "jobs", "value": collection_jobs}]},
        {"id": "assets", "title": "Live Assets", "value": aircraft_count + satellite_count, "status": "live", "items": [{"label": "aircraft", "value": aircraft_count}, {"label": "satellites", "value": satellite_count}]},
        {"id": "markets", "title": "Market Pressure", "value": market_signals, "status": "live" if market_signals else "quiet", "items": market.get("lanes", [])[:5]},
    ]
    try:
        recent_events = _maps_recent_spatial_events()
    except Exception:  # noqa: BLE001
        recent_events = []
    events = [
        {
            "id": str(row.get("vertex_id") or f"event-{idx}"),
            "title": str(row.get("description") or row.get("name") or row.get("event_type") or "SpatialEvent"),
            "category": str(row.get("event_type") or row.get("label") or "SpatialEvent"),
            "severity": str(row.get("severity") or "info"),
            "timestamp": str(row.get("created_at") or ""),
            "lat": row.get("lat"),
            "lng": row.get("lng"),
            "source": str(row.get("source") or ""),
        }
        for idx, row in enumerate(recent_events)
    ]
    return {
        **counts,
        "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "region": "global",
        "counts": counts,
        "risk": {
            "score": risk_score,
            "level": risk_level,
            "drivers": [
                f"{spatial_events} spatial events indexed" if spatial_events else "no recent event records",
                f"{infra_incidents} infrastructure incidents" if infra_incidents else "infrastructure incident count stable",
                f"{collection_jobs} collection jobs in graph" if collection_jobs else "no collection job backlog visible",
                f"{market_signals} market demand signals indexed" if market_signals else "market signal count quiet",
            ],
        },
        "layers": layers,
        "panels": panels,
        "events": events,
        "marketSignals": market,
        "source": "pod-langserver",
    }


def _risk_level(score: int) -> str:
    return "high" if score >= 70 else "elevated" if score >= 40 else "watch" if score >= 18 else "low"


def _world_monitor_coverage(counts: dict[str, Any]) -> dict[str, Any]:
    active = {
        "conflict-events": int(counts.get("spatialEvents") or 0) > 0,
        "military-adsb": True,
        "maritime-ais": int(counts.get("ports") or 0) > 0,
        "satellite-imagery": int(counts.get("satelliteScenes") or 0) > 0,
        "market-signals": int(counts.get("marketSignals") or 0) > 0,
        "ai-briefs": True,
        "country-instability": int(counts.get("places") or 0) > 0 or int(counts.get("infraIncidents") or 0) > 0,
    }
    covered = sum(1 for enabled in active.values() if enabled)
    total = len(active)
    gaps = [key for key, enabled in active.items() if not enabled]
    return {
        "target": "worldmonitor-style resident intelligence graph",
        "coveredCapabilities": covered,
        "totalCapabilities": total,
        "productCoveragePct": round(covered / total * 100),
        "implementationCoveragePct": 55,
        "gaps": gaps,
        "ddlFreeFacade": True,
    }


def _maps_intel_event_from_row(row: dict[str, Any], idx: int) -> dict[str, Any]:
    event_type = str(row.get("event_type") or row.get("label") or "SpatialEvent")
    severity = str(row.get("severity") or "info").lower()
    if severity not in {"critical", "high", "warning", "watch", "info", "low"}:
        severity = "info"
    title = str(row.get("description") or row.get("name") or event_type)
    return {
        "id": str(row.get("vertex_id") or f"intel-event-{idx}"),
        "title": title,
        "category": event_type,
        "severity": severity,
        "confidence": 0.55 if row.get("source") else 0.35,
        "timestamp": str(row.get("created_at") or ""),
        "geometry": {
            "type": "Point",
            "coordinates": [row.get("lng"), row.get("lat")],
        } if row.get("lat") is not None and row.get("lng") is not None else None,
        "sourceName": str(row.get("source") or "maps spatial graph"),
        "sourceUri": str(row.get("source") or ""),
        "links": [],
    }


def _maps_intel_events(payload: dict[str, Any]) -> dict[str, Any]:
    limit = _safe_int(payload.get("limit"), 25, 1, 200)
    rows = _maps_recent_spatial_events(limit)
    events = [_maps_intel_event_from_row(row, idx) for idx, row in enumerate(rows)]
    return {
        "events": events,
        "count": len(events),
        "asOfMs": int(time.time() * 1000),
        "source": "pod-langserver",
    }


def _maps_risk_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    dashboard = _maps_dashboard()
    counts = dict(dashboard.get("counts") or {})
    risk = dict(dashboard.get("risk") or {})
    score = int(risk.get("score") or 0)
    scope_kind = str(payload.get("scopeKind") or "global")
    scope_id = str(payload.get("scopeId") or dashboard.get("region") or "global")
    return {
        "snapshotId": f"maps-risk-{scope_kind}-{scope_id}-{int(time.time())}",
        "scopeKind": scope_kind,
        "scopeId": scope_id,
        "window": str(payload.get("window") or "24h"),
        "score": score,
        "level": str(risk.get("level") or _risk_level(score)),
        "trendDelta": 0,
        "confidence": 0.45,
        "eventCount": int(counts.get("spatialEvents") or 0),
        "drivers": list(risk.get("drivers") or []),
        "asOfMs": int(time.time() * 1000),
        "source": "pod-langserver",
    }


def _maps_latest_brief(payload: dict[str, Any]) -> dict[str, Any]:
    dashboard = _maps_dashboard()
    events = list(dashboard.get("events") or [])[:5]
    risk = dict(dashboard.get("risk") or {})
    counts = dict(dashboard.get("counts") or {})
    region = str(payload.get("region") or dashboard.get("region") or "global")
    headline = f"{region} risk is {risk.get('level', 'low')} at score {risk.get('score', 0)}"
    bullets = [
        f"{counts.get('spatialEvents', 0)} spatial events indexed",
        f"{counts.get('satelliteScenes', 0)} satellite scenes available",
        f"{counts.get('marketSignals', 0)} market demand signals indexed",
        f"{counts.get('airports', 0)} airports and {counts.get('ports', 0)} ports in graph coverage",
    ]
    if events:
        bullets.append(f"Latest event: {events[0].get('title')}")
    return {
        "briefId": f"maps-brief-{region}-{int(time.time())}",
        "title": "World Monitor-style maps intelligence brief",
        "headline": headline,
        "summary": "Resident graph brief generated from maps spatial events, infrastructure counts, live tracks, and imagery coverage.",
        "bullets": bullets,
        "citations": [
            {"id": str(event.get("id")), "title": str(event.get("title")), "source": str(event.get("source") or "")}
            for event in events
        ],
        "asOfMs": int(time.time() * 1000),
        "source": "pod-langserver",
    }


def _maps_intel_alerts(payload: dict[str, Any]) -> dict[str, Any]:
    snapshot = _maps_risk_snapshot(payload)
    score = int(snapshot.get("score") or 0)
    alerts: list[dict[str, Any]] = []
    if score >= 18:
        alerts.append(
            {
                "id": f"maps-alert-{snapshot['scopeKind']}-{snapshot['scopeId']}",
                "severity": str(snapshot.get("level") or _risk_level(score)),
                "title": "Spatial risk watch",
                "message": "; ".join(str(item) for item in snapshot.get("drivers", [])[:3]),
                "score": score,
                "status": "active",
                "asOfMs": snapshot["asOfMs"],
            }
        )
    return {
        "alerts": alerts,
        "count": len(alerts),
        "asOfMs": int(time.time() * 1000),
        "source": "pod-langserver",
    }


def _maps_world_monitor_dashboard(payload: dict[str, Any]) -> dict[str, Any]:
    dashboard = _maps_dashboard()
    counts = dict(dashboard.get("counts") or {})
    events = _maps_intel_events({"limit": payload.get("limit", 12)})
    risk_snapshot = _maps_risk_snapshot(payload)
    brief = _maps_latest_brief(payload)
    alerts = _maps_intel_alerts(payload)
    return {
        "fetchedAt": dashboard.get("fetchedAt"),
        "region": str(payload.get("region") or dashboard.get("region") or "global"),
        "counts": counts,
        "riskSnapshot": risk_snapshot,
        "coverage": _world_monitor_coverage(counts),
        "sourceFamilies": _WORLD_MONITOR_SOURCE_FAMILIES,
        "layers": dashboard.get("layers", []),
        "events": events["events"],
        "marketSignals": dashboard.get("marketSignals", {}),
        "brief": brief,
        "alerts": alerts["alerts"],
        "panels": dashboard.get("panels", []),
        "source": "pod-langserver",
    }


def _maps_degraded(nsid: str, error: Exception) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    if nsid.endswith(".listLiveAircraft"):
        return {"aircraft": [], "count": 0, "asOfMs": now_ms, "degraded": True, "error": str(error)}
    if nsid.endswith(".listLiveSatellites"):
        return {"satellites": [], "count": 0, "asOfMs": now_ms, "degraded": True, "error": str(error)}
    counts = {name: 0 for name in _MAPS_DASHBOARD_LABELS}
    if nsid.endswith(".listIntelEvents"):
        return {"events": [], "count": 0, "asOfMs": now_ms, "source": "pod-langserver", "degraded": True, "error": str(error)}
    if nsid.endswith(".getRiskSnapshot"):
        return {
            "snapshotId": f"maps-risk-degraded-{now_ms}",
            "scopeKind": "global",
            "scopeId": "global",
            "window": "24h",
            "score": 0,
            "level": "low",
            "trendDelta": 0,
            "confidence": 0,
            "eventCount": 0,
            "drivers": ["pod-side read unavailable"],
            "asOfMs": now_ms,
            "source": "pod-langserver",
            "degraded": True,
            "error": str(error),
        }
    if nsid.endswith(".getLatestBrief"):
        return {
            "briefId": f"maps-brief-degraded-{now_ms}",
            "title": "World Monitor-style maps intelligence brief",
            "headline": "maps intelligence graph unavailable",
            "summary": "Pod-side read facade could not reach the graph store.",
            "bullets": ["pod-side read unavailable"],
            "citations": [],
            "asOfMs": now_ms,
            "source": "pod-langserver",
            "degraded": True,
            "error": str(error),
        }
    if nsid.endswith(".listIntelAlerts"):
        return {"alerts": [], "count": 0, "asOfMs": now_ms, "source": "pod-langserver", "degraded": True, "error": str(error)}
    if nsid.endswith(".getWorldMonitorDashboard"):
        return {
            "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "region": "global",
            "counts": counts,
            "riskSnapshot": {
                "snapshotId": f"maps-risk-degraded-{now_ms}",
                "scopeKind": "global",
                "scopeId": "global",
                "window": "24h",
                "score": 0,
                "level": "low",
                "trendDelta": 0,
                "confidence": 0,
                "eventCount": 0,
                "drivers": ["pod-side read unavailable"],
                "asOfMs": now_ms,
                "source": "pod-langserver",
            },
            "coverage": _world_monitor_coverage(counts),
            "sourceFamilies": _WORLD_MONITOR_SOURCE_FAMILIES,
            "layers": [],
            "events": [],
            "brief": {
                "briefId": f"maps-brief-degraded-{now_ms}",
                "title": "World Monitor-style maps intelligence brief",
                "headline": "maps intelligence graph unavailable",
                "summary": "Pod-side read facade could not reach the graph store.",
                "bullets": ["pod-side read unavailable"],
                "citations": [],
                "asOfMs": now_ms,
                "source": "pod-langserver",
            },
            "alerts": [],
            "panels": [],
            "source": "pod-langserver",
            "degraded": True,
            "error": str(error),
        }
    return {
        **counts,
        "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "region": "global",
        "counts": counts,
        "risk": {"score": 0, "level": "low", "drivers": ["pod-side read unavailable"]},
        "layers": [],
        "panels": [],
        "events": [],
        "degraded": True,
        "error": str(error),
    }


@app.get("/")
def root() -> dict[str, Any]:
    return _base_status()


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return _base_status()


@app.get("/livez")
def livez() -> dict[str, Any]:
    return _base_status()


@app.get("/readyz")
def readyz() -> dict[str, Any]:
    status = _base_status()
    status["ready"] = True
    return status


@app.get("/tools")
def tools() -> dict[str, Any]:
    from kotodama.mcp_dispatch import build_default_handlers

    handlers = build_default_handlers()
    return {"ok": True, "count": len(handlers), "tools": sorted(handlers)}


@app.post("/invoke")
async def invoke(req: InvokeRequest) -> dict[str, Any]:
    from kotodama.mcp_dispatch import build_default_handlers, handle_envelope

    envelope = {"method": "tools/call", "params": {"name": req.name, "arguments": req.arguments}}
    status, body = await handle_envelope(envelope, build_default_handlers())
    if status >= 400:
        return {"ok": False, "status": status, **body}
    return {"ok": True, **body}


@app.post("/mcp")
async def mcp(req: McpEnvelopeRequest) -> dict[str, Any]:
    from kotodama.mcp_dispatch import build_default_handlers, handle_envelope

    envelope = req.dict(exclude_none=True)
    status, body = await handle_envelope(envelope, build_default_handlers())
    response: dict[str, Any] = {"ok": status < 400, "status": status, **body}
    if req.id is not None:
        response["id"] = req.id
    if req.jsonrpc:
        response["jsonrpc"] = req.jsonrpc
    return response


@app.post("/runs")
async def runs(body: dict[str, Any]) -> dict[str, Any]:
    """Small LangGraph-compatible sync run endpoint for single MCP tools."""
    assistant_id = str(body.get("assistant_id") or body.get("graph") or body.get("name") or "")
    payload = body.get("input") if isinstance(body.get("input"), dict) else {}
    if not assistant_id:
        return {"ok": False, "error": "assistant_id, graph, or name is required"}
    result = await invoke(InvokeRequest(name=assistant_id, arguments=payload))
    return {
        "ok": bool(result.get("ok")),
        "assistant_id": assistant_id,
        "output": result.get("result") if result.get("ok") else {},
        "error": result.get("error"),
    }


@app.get("/metrics")
def metrics() -> Response:
    if generate_latest is not None:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    body = (
        "# HELP kotodama_worker_api_up Whether the kotodama worker API process is running.\n"
        "# TYPE kotodama_worker_api_up gauge\n"
        f'kotodama_worker_api_up{{component="{_COMPONENT}",runtime_kind="{_RUNTIME_KIND}"}} 1\n'
    )
    return Response(body, media_type=CONTENT_TYPE_LATEST)


# SSE-aware ameno subscribeBriefs route — must precede the catch-all xrpc route.
@app.get("/xrpc/com.etzhayyim.apps.ameno.subscribeBriefs")
async def ameno_subscribe_briefs(request: Request) -> StreamingResponse:
    """com.etzhayyim.apps.ameno.subscribeBriefs — SSE stream of NATS commit events.

    Browsers open EventSource against this endpoint (via the PDS pipethrough).
    Each frame is `event: brief\\ndata: {...}\\n\\n`; stream ends with `done`.
    """
    from kotodama.ameno_handlers import subscribe_briefs_sse

    payload = dict(request.query_params)
    return StreamingResponse(
        subscribe_briefs_sse(payload),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache, no-transform",
            "x-accel-buffering": "no",
            "connection": "keep-alive",
        },
    )


@app.api_route("/xrpc/{nsid:path}", methods=["GET", "POST"])
async def xrpc(nsid: str, request: Request) -> dict[str, Any]:
    """Pod-side XRPC facade for read-only LangServer-backed actor methods."""
    payload = await _request_payload(request)
    try:
        if nsid == "com.etzhayyim.apps.maps.getDashboard":
            return _maps_dashboard()
        if nsid == "com.etzhayyim.apps.maps.listLiveAircraft":
            return _maps_list_live_aircraft(payload)
        if nsid == "com.etzhayyim.apps.maps.listLiveSatellites":
            return _maps_list_live_satellites(payload)
        if nsid == "com.etzhayyim.apps.maps.getWorldMonitorDashboard":
            return _maps_world_monitor_dashboard(payload)
        if nsid == "com.etzhayyim.apps.maps.listIntelEvents":
            return _maps_intel_events(payload)
        if nsid == "com.etzhayyim.apps.maps.getRiskSnapshot":
            return _maps_risk_snapshot(payload)
        if nsid == "com.etzhayyim.apps.maps.getLatestBrief":
            return _maps_latest_brief(payload)
        if nsid == "com.etzhayyim.apps.maps.listIntelAlerts":
            return _maps_intel_alerts(payload)
        if nsid == "com.etzhayyim.apps.ameno.saveResult":
            from kotodama.ameno_handlers import handle_save_result

            return handle_save_result(payload)
        if nsid == "com.etzhayyim.apps.ameno.listHistory":
            from kotodama.ameno_handlers import handle_list_history

            return handle_list_history(payload)
        if nsid == "com.etzhayyim.apps.ameno.listActorAdapters":
            from kotodama.ameno_handlers import handle_list_actor_adapters

            return handle_list_actor_adapters(payload)
        if nsid == "com.etzhayyim.apps.ameno.listMyCredits":
            from kotodama.ameno_handlers import handle_list_my_credits

            return handle_list_my_credits(payload)
    except Exception as exc:  # noqa: BLE001
        return _maps_degraded(nsid, exc)
    return {"ok": False, "error": "unsupported_nsid", "nsid": nsid}


def main() -> None:
    host = os.environ.get("WORKER_API_HOST", "0.0.0.0")
    port = os.environ.get("WORKER_API_PORT", "8081")
    argv = [
        "granian",
        "--interface",
        "asgi",
        "--host",
        host,
        "--port",
        port,
        "kotodama.worker_api:app",
    ]
    os.execvp("granian", argv)


if __name__ == "__main__":
    main()
