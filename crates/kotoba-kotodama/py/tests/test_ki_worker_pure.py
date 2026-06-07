"""Pure-logic tests for ki_worker_main (no DB or network)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


# ─── helpers ──────────────────────────────────────────────────────────────


def test_uid_prefix():
    from kotodama.ki_worker_main import _uid

    a = _uid("xyl")
    b = _uid("art")
    assert a.startswith("xyl-")
    assert b.startswith("art-")
    assert a != b


def test_now_iso():
    from kotodama.ki_worker_main import _now

    ts = _now()
    assert "T" in ts
    assert ts.endswith("+00:00") or "+" in ts


# ─── task_absorb ──────────────────────────────────────────────────────────


def test_absorb_scan_empty():
    """Scan mode with no pending rows returns status='empty'."""
    with patch("kotodama.ki_worker_main.fetch_one", return_value=None):
        from kotodama.ki_worker_main import task_absorb

        result = _run(task_absorb())

    assert result["absorbId"] == ""
    assert result["status"] == "empty"


def test_absorb_scan_returns_pending():
    """Scan mode with a pending row returns its ID and status='absorbed'."""
    row = ("at://ki.etzhayyim.com/com.etzhayyim.apps.ki.absorb/xyl-deadbeef",)
    with patch("kotodama.ki_worker_main.fetch_one", return_value=row):
        from kotodama.ki_worker_main import task_absorb

        result = _run(task_absorb())

    assert result["absorbId"] == "xyl-deadbeef"
    assert result["status"] == "absorbed"


def test_absorb_by_content():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("kotodama.ki_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.ki_worker_main import task_absorb

        result = _run(task_absorb(
            sourceVertexId="at://koke.etzhayyim.com/com.etzhayyim.apps.koke.fixation/kox-abc",
            inputKind="text",
            content="sample knowledge content",
        ))

    assert result["absorbId"].startswith("xyl-")
    assert result["status"] == "absorbed"
    assert result["contentHash"]
    assert result["absorbedAt"]


def test_absorb_hash_deterministic():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("kotodama.ki_worker_main.sync_cursor", return_value=mock_cm):
        from kotodama.ki_worker_main import task_absorb

        r1 = _run(task_absorb(content="identical content"))
        r2 = _run(task_absorb(content="identical content"))

    assert r1["contentHash"] == r2["contentHash"]


# ─── task_synthesize ──────────────────────────────────────────────────────


def test_synthesize_no_input():
    from kotodama.ki_worker_main import task_synthesize

    result = _run(task_synthesize())
    assert "error" in result


def test_synthesize_valid_langgraph_response():
    """task_synthesize delegates to ki_synthesis_graph.synthesize (LangGraph pipeline)."""
    mock_graph = MagicMock(return_value={
        "synthesis": "insight text",
        "title": "Test",
        "keyPoints": ["a", "b"],
        "confidence": 0.82,
        "artifactKind": "insight",
        "refined": False,
        "latencyMs": 100,
        "error": "",
    })
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch("kotodama.primitives.ki_synthesis_graph.synthesize", mock_graph),
        patch("kotodama.ki_worker_main.sync_cursor", return_value=mock_cm),
        patch("kotodama.ki_worker_main.fetch_one", return_value=None),
    ):
        from kotodama.ki_worker_main import task_synthesize

        result = _run(task_synthesize(
            absorbId="xyl-abc",
            content="some knowledge to synthesize",
        ))

    assert result["artifactId"].startswith("art-")
    assert result["artifactKind"] == "insight"
    assert result["confidence"] == 0.82
    assert result["absorbId"] == "xyl-abc"
    assert result["refined"] is False


def test_synthesize_low_confidence_triggers_refine():
    """Confidence below REFINE_THRESHOLD causes the graph to set refined=True."""
    mock_graph = MagicMock(return_value={
        "synthesis": "refined insight",
        "title": "",
        "keyPoints": [],
        "confidence": 0.75,
        "artifactKind": "insight",
        "refined": True,
        "latencyMs": 200,
        "error": "",
    })
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch("kotodama.primitives.ki_synthesis_graph.synthesize", mock_graph),
        patch("kotodama.ki_worker_main.sync_cursor", return_value=mock_cm),
        patch("kotodama.ki_worker_main.fetch_one", return_value=None),
    ):
        from kotodama.ki_worker_main import task_synthesize

        result = _run(task_synthesize(content="some content"))

    assert result["artifactId"].startswith("art-")
    assert result["confidence"] == 0.75
    assert result["refined"] is True


# ─── task_bloom ───────────────────────────────────────────────────────────


def test_bloom_no_artifact_id():
    from kotodama.ki_worker_main import task_bloom

    result = _run(task_bloom())
    assert "error" in result


def test_bloom_not_found():
    with patch("kotodama.ki_worker_main.fetch_one", return_value=None):
        from kotodama.ki_worker_main import task_bloom

        result = _run(task_bloom(artifactId="art-missing"))
    assert "error" in result


def test_bloom_low_confidence_skips():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    # confidence 0.3 is below default cutoff 0.6
    row = ("at://ki.etzhayyim.com/com.etzhayyim.apps.ki.artifact/art-abc", 0.3)

    with (
        patch("kotodama.ki_worker_main.fetch_one", return_value=row),
        patch("kotodama.ki_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.ki_worker_main import task_bloom

        result = _run(task_bloom(artifactId="art-abc"))

    assert result["bloomed"] is False
    assert "confidence" in result["reason"]


def test_bloom_success():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    row = ("at://ki.etzhayyim.com/com.etzhayyim.apps.ki.artifact/art-abc", 0.85)

    with (
        patch("kotodama.ki_worker_main.fetch_one", return_value=row),
        patch("kotodama.ki_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.ki_worker_main import task_bloom

        result = _run(task_bloom(artifactId="art-abc"))

    assert result["bloomed"] is True
    assert result["artifactId"] == "art-abc"
    assert result["publishedAt"]


# ─── task_ring ────────────────────────────────────────────────────────────


def test_ring_creates_checkpoint():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch("kotodama.ki_worker_main.fetch_one", return_value=(42,)),
        patch("kotodama.ki_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.ki_worker_main import task_ring

        result = _run(task_ring(period="P1D"))

    assert result["ringId"].startswith("ring-")
    assert result["period"] == "P1D"
    assert result["snapshotCount"] == 42
    assert result["ringAt"]


def test_ring_default_period():
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock())
    mock_cm.__exit__ = MagicMock(return_value=False)

    with (
        patch("kotodama.ki_worker_main.fetch_one", return_value=(0,)),
        patch("kotodama.ki_worker_main.sync_cursor", return_value=mock_cm),
    ):
        from kotodama.ki_worker_main import task_ring

        result = _run(task_ring())

    assert result["period"] == "P1D"
    assert result["ringId"].startswith("ring-")
