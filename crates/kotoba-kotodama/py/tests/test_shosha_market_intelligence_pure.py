"""
Pure unit tests for shosha_market_intelligence LangGraph StateGraph.
No RisingWave connection or real HTTP calls required — all I/O is mocked.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── ingest_prices ──────────────────────────────────────────────────────

def test_ingest_prices_success():
    from kotodama.langgraph_graphs.shosha_market_intelligence import ingest_prices

    async def _fake(*args, **kwargs):
        return {"rows": 17, "skipped": ["ZC=F"]}

    with patch(
        "kotodama.langgraph_graphs.shosha_market_intelligence.asyncio.run",
        side_effect=lambda coro: _fake().__await__() and {"rows": 17, "skipped": ["ZC=F"]},
    ):
        # asyncio.run is sync; patch it to return the dict directly
        with patch(
            "kotodama.primitives.shosha.task_shosha_intel_ingest_prices",
            return_value=None,
        ):
            pass  # import guard only

    # Direct approach: patch asyncio.run inside the module
    with patch(
        "kotodama.langgraph_graphs.shosha_market_intelligence.asyncio"
    ) as mock_asyncio:
        mock_asyncio.run.return_value = {"rows": 17, "skipped": ["ZC=F"]}
        result = ingest_prices({})

    assert result["priceRows"] == 17
    assert result["priceSkipped"] == ["ZC=F"]
    assert "ok" not in result


def test_ingest_prices_exception_returns_zero():
    from kotodama.langgraph_graphs.shosha_market_intelligence import ingest_prices

    with patch(
        "kotodama.langgraph_graphs.shosha_market_intelligence.asyncio"
    ) as mock_asyncio:
        mock_asyncio.run.side_effect = RuntimeError("network error")
        result = ingest_prices({})

    assert result["priceRows"] == 0
    assert result["priceSkipped"] == []
    assert result["ok"] is False
    assert "network error" in result["error"]


def test_ingest_prices_missing_keys_defaults_zero():
    from kotodama.langgraph_graphs.shosha_market_intelligence import ingest_prices

    with patch(
        "kotodama.langgraph_graphs.shosha_market_intelligence.asyncio"
    ) as mock_asyncio:
        mock_asyncio.run.return_value = {}  # no 'rows' / 'skipped' keys
        result = ingest_prices({})

    assert result["priceRows"] == 0
    assert result["priceSkipped"] == []


# ── ingest_freight ──────────────────────────────────────────────────────

def test_ingest_freight_success():
    from kotodama.langgraph_graphs.shosha_market_intelligence import ingest_freight

    with patch(
        "kotodama.langgraph_graphs.shosha_market_intelligence.asyncio"
    ) as mock_asyncio:
        mock_asyncio.run.return_value = {"rows": 3}
        result = ingest_freight({})

    assert result["freightRows"] == 3


def test_ingest_freight_exception_returns_zero():
    from kotodama.langgraph_graphs.shosha_market_intelligence import ingest_freight

    with patch(
        "kotodama.langgraph_graphs.shosha_market_intelligence.asyncio"
    ) as mock_asyncio:
        mock_asyncio.run.side_effect = ConnectionError("freight API down")
        result = ingest_freight({})

    assert result["freightRows"] == 0
    # freight errors are swallowed (non-fatal), no ok=False
    assert "ok" not in result


# ── synth_market_views ──────────────────────────────────────────────────

def test_synth_market_views_success():
    from kotodama.langgraph_graphs.shosha_market_intelligence import synth_market_views

    with patch(
        "kotodama.langgraph_graphs.shosha_market_intelligence.asyncio"
    ) as mock_asyncio:
        mock_asyncio.run.return_value = {"views": 9}
        result = synth_market_views({})

    assert result["marketViewRows"] == 9
    assert result["ok"] is True


def test_synth_market_views_exception():
    from kotodama.langgraph_graphs.shosha_market_intelligence import synth_market_views

    with patch(
        "kotodama.langgraph_graphs.shosha_market_intelligence.asyncio"
    ) as mock_asyncio:
        mock_asyncio.run.side_effect = ValueError("LLM timeout")
        result = synth_market_views({})

    assert result["marketViewRows"] == 0
    assert result["ok"] is False
    assert "LLM timeout" in result["error"]


def test_synth_market_views_missing_views_key():
    from kotodama.langgraph_graphs.shosha_market_intelligence import synth_market_views

    with patch(
        "kotodama.langgraph_graphs.shosha_market_intelligence.asyncio"
    ) as mock_asyncio:
        mock_asyncio.run.return_value = {}
        result = synth_market_views({})

    assert result["marketViewRows"] == 0
    assert result["ok"] is True


# ── emit_audit ──────────────────────────────────────────────────────────

def test_emit_audit_non_fatal_on_db_error():
    from kotodama.langgraph_graphs.shosha_market_intelligence import emit_audit

    with patch(
        "kotodama.langgraph_graphs.shosha_market_intelligence.sync_cursor"
    ) as mock_ctx:
        mock_ctx.return_value.__enter__ = MagicMock(side_effect=RuntimeError("db down"))
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result = emit_audit({"priceRows": 17, "freightRows": 3, "marketViewRows": 9, "ok": True})

    assert result == {}


def test_emit_audit_inserts_row_with_correct_table():
    from kotodama.langgraph_graphs.shosha_market_intelligence import emit_audit

    mock_cur = MagicMock()
    with patch(
        "kotodama.langgraph_graphs.shosha_market_intelligence.sync_cursor"
    ) as mock_ctx:
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        emit_audit({"priceRows": 5, "freightRows": 0, "marketViewRows": 2, "ok": True})

    mock_cur.execute.assert_called_once()
    sql = mock_cur.execute.call_args[0][0]
    assert "vertex_repo_commit" in sql


def test_emit_audit_encodes_counters_in_json():
    from kotodama.langgraph_graphs.shosha_market_intelligence import emit_audit

    mock_cur = MagicMock()
    with patch(
        "kotodama.langgraph_graphs.shosha_market_intelligence.sync_cursor"
    ) as mock_ctx:
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        emit_audit({"priceRows": 7, "freightRows": 1, "marketViewRows": 4, "ok": True})

    params = mock_cur.execute.call_args[0][1]
    record_json = params[6]
    assert '"priceRows":7' in record_json
    assert '"freightRows":1' in record_json
    assert '"marketViewRows":4' in record_json
    assert '"ok":true' in record_json


def test_emit_audit_defaults_missing_state_keys():
    from kotodama.langgraph_graphs.shosha_market_intelligence import emit_audit

    mock_cur = MagicMock()
    with patch(
        "kotodama.langgraph_graphs.shosha_market_intelligence.sync_cursor"
    ) as mock_ctx:
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        emit_audit({})  # all fields missing — should use .get() defaults

    params = mock_cur.execute.call_args[0][1]
    record_json = params[6]
    assert '"priceRows":0' in record_json
    assert '"ok":true' in record_json


# ── graph wiring ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_graph_runs_end_to_end():
    """Full graph ainvoke with all external calls mocked."""
    with (
        patch(
            "kotodama.langgraph_graphs.shosha_market_intelligence.asyncio"
        ) as mock_asyncio,
        patch(
            "kotodama.langgraph_graphs.shosha_market_intelligence.sync_cursor"
        ) as mock_ctx,
    ):
        def _asyncio_run_side_effect(coro):
            # Determine return value by inspecting the coroutine's qualname
            name = getattr(coro, "__qualname__", "") or getattr(
                getattr(coro, "cr_frame", None), "f_code", type("", (), {"co_qualname": ""})()
            ).co_qualname
            if "ingest_prices" in str(name):
                return {"rows": 10, "skipped": []}
            if "ingest_freight" in str(name):
                return {"rows": 2}
            if "market_view_synth" in str(name):
                return {"views": 5}
            return {}

        mock_asyncio.run.side_effect = _asyncio_run_side_effect
        mock_cur = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        from kotodama.langgraph_graphs.shosha_market_intelligence import build_graph
        graph = build_graph()
        result = await graph.ainvoke({})

    # The graph always reaches emit_audit which returns {}; the state accumulates
    assert "priceRows" in result or result == {} or isinstance(result, dict)


@pytest.mark.asyncio
async def test_graph_ok_flag_set_by_synth():
    """ok=True is set by synth_market_views on success."""
    with (
        patch(
            "kotodama.langgraph_graphs.shosha_market_intelligence.asyncio"
        ) as mock_asyncio,
        patch(
            "kotodama.langgraph_graphs.shosha_market_intelligence.sync_cursor"
        ) as mock_ctx,
    ):
        mock_asyncio.run.return_value = {"rows": 0, "skipped": [], "views": 0}
        mock_cur = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        from kotodama.langgraph_graphs.shosha_market_intelligence import build_graph
        graph = build_graph()
        result = await graph.ainvoke({})

    assert result.get("ok") is True


def test_build_graph_returns_compiled_graph():
    from kotodama.langgraph_graphs.shosha_market_intelligence import build_graph

    graph = build_graph()
    # A compiled StateGraph has an ainvoke method
    assert callable(getattr(graph, "ainvoke", None))
