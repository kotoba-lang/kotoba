from __future__ import annotations

from fastapi.testclient import TestClient

from kotodama import worker_api


def test_worker_api_health_routes() -> None:
    client = TestClient(worker_api.app)

    for path in ("/healthz", "/readyz", "/livez"):
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["component"]
        assert body["runtimeKind"]


def test_worker_api_metrics_route() -> None:
    client = TestClient(worker_api.app)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "kotodama_worker_api_up" in response.text


def test_worker_api_maps_live_degrades_without_rw(monkeypatch) -> None:
    def boom():
        raise RuntimeError("RW_URL missing")

    monkeypatch.setattr(worker_api, "_sync_cursor", boom)
    client = TestClient(worker_api.app)

    response = client.post("/xrpc/com.etzhayyim.apps.maps.listLiveAircraft", json={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["aircraft"] == []
    assert body["count"] == 0
    assert body["degraded"] is True


def test_worker_api_maps_dashboard_degrades_without_rw(monkeypatch) -> None:
    def boom():
        raise RuntimeError("RW_URL missing")

    monkeypatch.setattr(worker_api, "_sync_cursor", boom)
    client = TestClient(worker_api.app)

    response = client.post("/xrpc/com.etzhayyim.apps.maps.getDashboard", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["places"] == 0
    assert body["risk"]["level"] == "low"
    assert body["degraded"] is True


def test_worker_api_maps_world_monitor_dashboard_degrades_without_rw(monkeypatch) -> None:
    def boom():
        raise RuntimeError("RW_URL missing")

    monkeypatch.setattr(worker_api, "_sync_cursor", boom)
    client = TestClient(worker_api.app)

    response = client.post("/xrpc/com.etzhayyim.apps.maps.getWorldMonitorDashboard", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["riskSnapshot"]["level"] == "low"
    assert body["coverage"]["target"] == "worldmonitor-style resident intelligence graph"
    assert body["brief"]["citations"] == []
    assert body["degraded"] is True


def test_worker_api_maps_world_monitor_dashboard_from_existing_graph(monkeypatch) -> None:
    def fake_count(label: str) -> int:
        return {
            "Place": 10,
            "Port": 2,
            "SpatialEvent": 3,
            "SatelliteScene": 4,
            "CollectionJob": 1,
        }.get(label, 0)

    def fake_aircraft(payload: dict[str, object]) -> dict[str, object]:
        return {"aircraft": [{"icao24": "abc123"}], "count": 1, "asOfMs": 1, "source": "pod-langserver"}

    def fake_satellites(payload: dict[str, object]) -> dict[str, object]:
        return {"satellites": [], "count": 0, "asOfMs": 1, "source": "pod-langserver"}

    def fake_events(limit: int = 8) -> list[dict[str, object]]:
        return [
            {
                "vertex_id": "event-1",
                "label": "SpatialEvent",
                "name": "port disruption",
                "event_type": "incident",
                "severity": "watch",
                "lat": 35.0,
                "lng": 139.0,
                "source": "test-source",
                "created_at": "2026-05-14T00:00:00Z",
            }
        ][:limit]

    def fake_market(limit: int = 5) -> dict[str, object]:
        return {
            "count": 2,
            "lanes": [{"lane": "bpmn", "count": 2, "magnitude": 3.0}],
            "signals": [],
        }

    monkeypatch.setattr(worker_api, "_maps_count_label", fake_count)
    monkeypatch.setattr(worker_api, "_maps_list_live_aircraft", fake_aircraft)
    monkeypatch.setattr(worker_api, "_maps_list_live_satellites", fake_satellites)
    monkeypatch.setattr(worker_api, "_maps_recent_spatial_events", fake_events)
    monkeypatch.setattr(worker_api, "_maps_market_signal_summary", fake_market)
    client = TestClient(worker_api.app)

    response = client.post("/xrpc/com.etzhayyim.apps.maps.getWorldMonitorDashboard", json={"limit": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "pod-langserver"
    assert body["events"][0]["geometry"]["coordinates"] == [139.0, 35.0]
    assert body["counts"]["marketSignals"] == 2
    assert body["brief"]["citations"][0]["id"] == "event-1"
    assert body["coverage"]["productCoveragePct"] == 100


def test_worker_api_maps_list_intel_events_degrades_without_rw(monkeypatch) -> None:
    def boom():
        raise RuntimeError("RW_URL missing")

    monkeypatch.setattr(worker_api, "_sync_cursor", boom)
    client = TestClient(worker_api.app)

    response = client.post("/xrpc/com.etzhayyim.apps.maps.listIntelEvents", json={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["events"] == []
    assert body["count"] == 0
    assert body["degraded"] is True
