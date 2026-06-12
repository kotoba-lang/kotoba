"""Pure-logic tests for graph_sos_intel_worker_main (no DB or network)."""

from __future__ import annotations

import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# ─── helpers ──────────────────────────────────────────────────────────────


def test_gen_id_prefix():
    from kotodama.graph_sos_intel_worker_main import _gen_id

    snap_id = _gen_id("snap")
    assert snap_id.startswith("snap-")
    assert len(snap_id) > 10

    fnd_id = _gen_id("fnd")
    assert fnd_id.startswith("fnd-")
    assert snap_id != fnd_id


def test_now_is_iso():
    from kotodama.graph_sos_intel_worker_main import _now

    ts = _now()
    assert "T" in ts
    assert ts.endswith("+00:00") or ts.endswith("Z") or "+" in ts


# ─── inventoryCatalog ────────────────────────────────────────────────────


def _run(coro):
    return asyncio.run(coro)


def test_inventory_catalog_counts():
    """inventoryCatalog classifies rows by prefix/type correctly."""
    mock_relations = [
        ("public", "vertex_foo", "BASE TABLE", "YES"),
        ("public", "vertex_bar", "BASE TABLE", "YES"),
        ("public", "edge_x", "BASE TABLE", "NO"),
        ("public", "mv_baz", "MATERIALIZED VIEW", "NO"),
    ]
    mock_indexes = [
        ("public", "vertex_foo", "idx_foo_vid", "CREATE INDEX ..."),
    ]

    with patch(
        "kotodama.graph_sos_intel_worker_main.fetch_all",
        side_effect=[mock_relations, mock_indexes],
    ):
        from kotodama.graph_sos_intel_worker_main import task_inventory_catalog

        result = _run(task_inventory_catalog())

    assert result["vertexTableCount"] == 2
    assert result["edgeTableCount"] == 1
    assert result["mvCount"] == 1
    assert result["idxCount"] == 1
    assert result["relationTotal"] == 4
    assert len(result["relations"]) == 4
    assert result["relations"][0]["name"] == "vertex_foo"


# ─── detectFindings ──────────────────────────────────────────────────────


def test_detect_findings_no_prev():
    """No previous snapshot → no findings."""
    with (
        patch("kotodama.graph_sos_intel_worker_main.fetch_one", return_value=None),
        patch("kotodama.graph_sos_intel_worker_main.sync_cursor"),
    ):
        from kotodama.graph_sos_intel_worker_main import task_detect_findings

        result = _run(task_detect_findings(
            snapshotId="snap-abc",
            vertexTableCount=100,
            edgeTableCount=20,
            mvCount=5,
        ))
    assert result["findingCount"] == 0
    assert result["findings"] == []


def test_detect_findings_large_delta():
    """Large vertex count delta triggers a finding."""
    prev_row = ("snap-old", 80, 20, 5)

    mock_cursor_cm = MagicMock()
    mock_cursor_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cursor_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch(
            "kotodama.graph_sos_intel_worker_main.fetch_one",
            return_value=prev_row,
        ),
        patch(
            "kotodama.graph_sos_intel_worker_main.sync_cursor",
            return_value=mock_cursor_cm,
        ),
    ):
        from kotodama.graph_sos_intel_worker_main import task_detect_findings

        result = _run(task_detect_findings(
            snapshotId="snap-new",
            vertexTableCount=110,
            edgeTableCount=20,
            mvCount=5,
        ))

    # delta = 30 (> threshold 5) → at least 1 finding
    assert result["findingCount"] >= 1


# ─── queryLatestSnapshot ─────────────────────────────────────────────────


def test_query_latest_snapshot_not_found():
    with patch("kotodama.graph_sos_intel_worker_main.fetch_one", return_value=None):
        from kotodama.graph_sos_intel_worker_main import task_query_latest_snapshot

        result = _run(task_query_latest_snapshot())
    assert result["snapshotFound"] is False


def test_query_latest_snapshot_found():
    row = ("snap-123", 500, 200, 50, 10, 800, 0, "2026-05-07T00:00:00Z")
    with patch("kotodama.graph_sos_intel_worker_main.fetch_one", return_value=row):
        from kotodama.graph_sos_intel_worker_main import task_query_latest_snapshot

        result = _run(task_query_latest_snapshot())
    assert result["snapshotFound"] is True
    assert result["snapshotId"] == "snap-123"
    assert result["vertexTableCount"] == 200


# ─── generateBriefing ────────────────────────────────────────────────────


def test_generate_briefing_no_snapshot():
    from kotodama.graph_sos_intel_worker_main import task_generate_briefing

    result = _run(task_generate_briefing(snapshotFound=False))
    assert "No topology snapshot" in result["briefingText"]
    assert result["severity"] == "info"


def test_generate_briefing_with_snapshot():
    mock_llm = MagicMock(return_value={"content": "Graph looks healthy. 500 relations.", "finish": "stop"})
    with patch("kotodama.llm.call_tier", mock_llm):
        from kotodama.graph_sos_intel_worker_main import task_generate_briefing

        result = _run(task_generate_briefing(
            snapshotFound=True,
            snapshotId="snap-abc",
            relationTotal=500,
            vertexTableCount=200,
            edgeTableCount=50,
            mvCount=10,
            idxCount=800,
            anomalyCount=0,
            snapshotCreatedAt="2026-05-07T00:00:00Z",
        ))

    assert "healthy" in result["briefingText"].lower() or result["briefingText"]
    assert result["severity"] == "info"
    assert result["snapshotId"] == "snap-abc"


def test_generate_briefing_with_anomalies():
    mock_llm = MagicMock(return_value={"content": "3 anomalies detected.", "finish": "stop"})
    with patch("kotodama.llm.call_tier", mock_llm):
        from kotodama.graph_sos_intel_worker_main import task_generate_briefing

        result = _run(task_generate_briefing(
            snapshotFound=True,
            snapshotId="snap-xyz",
            relationTotal=500,
            vertexTableCount=200,
            edgeTableCount=50,
            mvCount=10,
            idxCount=800,
            anomalyCount=3,
            snapshotCreatedAt="2026-05-07T00:00:00Z",
        ))

    assert result["severity"] == "warning"


# ─── writeFinding ────────────────────────────────────────────────────────


def test_write_finding_empty_briefing():
    from kotodama.graph_sos_intel_worker_main import task_write_finding

    result = _run(task_write_finding(briefingText="", severity="info"))
    assert result["written"] is False


def test_write_finding_persists():
    mock_cursor_cm = MagicMock()
    mock_cursor_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cursor_cm.__exit__ = MagicMock(return_value=False)

    with patch(
        "kotodama.graph_sos_intel_worker_main.sync_cursor",
        return_value=mock_cursor_cm,
    ):
        from kotodama.graph_sos_intel_worker_main import task_write_finding

        result = _run(task_write_finding(
            briefingText="Graph is healthy.", severity="info", snapshotId="snap-abc"
        ))

    assert result["written"] is True
    assert result["findingId"].startswith("fnd-")
    assert "graph-sos-intel.etzhayyim.com" in result["vertexId"]
