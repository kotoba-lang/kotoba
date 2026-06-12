"""
Pure unit tests for shosha_agent_loop LangGraph StateGraph.
No RisingWave connection or LLM call required — DB and LLM are mocked.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── helpers ────────────────────────────────────────────────────────────

def _make_state(**kwargs):
    return {"prompt": "What is the WTI outlook?", "tier": "reasoning", **kwargs}


# ── fetch_context ──────────────────────────────────────────────────────

def test_fetch_context_empty_rw():
    from kotodama.langgraph_graphs.shosha_agent_loop import fetch_context

    with patch("kotodama.langgraph_graphs.shosha_agent_loop._rw_query", return_value=[]):
        result = fetch_context(_make_state())

    assert result["_context"] == "(no context rows yet)"
    assert result["intelRowsUsed"] == 0
    assert result["marketViewRowsUsed"] == 0
    assert result["exposureRowsUsed"] == 0


def test_fetch_context_with_rows():
    from kotodama.langgraph_graphs.shosha_agent_loop import fetch_context

    def _mock_query(sql, params=()):
        if "vertex_shosha_intel" in sql:
            return [("CL=F", 80.5, "USD", 1000)]
        if "vertex_shosha_market_view" in sql:
            return [("WTI", "bullish", 0.75, 85.0, "supply cut")]
        if "mv_shosha_exposure_by_commodity" in sql:
            return [("WTI", 9_650_000)]
        return []

    with patch("kotodama.langgraph_graphs.shosha_agent_loop._rw_query", side_effect=_mock_query):
        result = fetch_context(_make_state())

    assert result["intelRowsUsed"] == 1
    assert result["marketViewRowsUsed"] == 1
    assert result["exposureRowsUsed"] == 1
    assert "CL=F" in result["_context"]
    assert "bullish" in result["_context"]
    assert "WTI" in result["_context"]


def test_fetch_context_commodity_focus():
    """commodityFocus is passed through to queries."""
    from kotodama.langgraph_graphs.shosha_agent_loop import fetch_context

    calls: list[tuple] = []

    def _capturing_query(sql, params=()):
        calls.append((sql, params))
        return []

    with patch("kotodama.langgraph_graphs.shosha_agent_loop._rw_query", side_effect=_capturing_query):
        fetch_context(_make_state(commodityFocus="WTI"))

    # All three queries should have received the focus param
    for _, params in calls:
        assert params == ("WTI",), f"expected ('WTI',), got {params}"


# ── call_llm ───────────────────────────────────────────────────────────

def test_call_llm_success():
    from kotodama.langgraph_graphs.shosha_agent_loop import call_llm

    mock_resp = {"content": "WTI looks bullish.", "model": "qwen3", "latencyMs": 450}
    with patch("kotodama.langgraph_graphs.shosha_agent_loop.llm") as mock_llm:
        mock_llm.call_tier.return_value = mock_resp
        result = call_llm(_make_state(_context="some context"))

    assert result["ok"] is True
    assert result["content"] == "WTI looks bullish."
    assert result["model"] == "qwen3"
    assert result["latencyMs"] == 450


def test_call_llm_strips_think_blocks():
    from kotodama.langgraph_graphs.shosha_agent_loop import call_llm

    raw = "<think>internal reasoning</think>WTI looks bullish."
    with patch("kotodama.langgraph_graphs.shosha_agent_loop.llm") as mock_llm:
        mock_llm.call_tier.return_value = {"content": raw, "model": "m", "latencyMs": 0}
        result = call_llm(_make_state(_context="ctx"))

    assert "<think>" not in result["content"]
    assert "WTI looks bullish." in result["content"]


def test_call_llm_missing_prompt():
    from kotodama.langgraph_graphs.shosha_agent_loop import call_llm

    result = call_llm({"_context": "ctx"})
    assert result["ok"] is False
    assert "prompt" in result["error"]


def test_call_llm_llm_error():
    from kotodama.langgraph_graphs.shosha_agent_loop import call_llm

    with patch("kotodama.langgraph_graphs.shosha_agent_loop.llm") as mock_llm:
        mock_llm.LlmError = Exception
        mock_llm.call_tier.side_effect = Exception("LLM timeout")
        result = call_llm(_make_state(_context="ctx"))

    assert result["ok"] is False
    assert "LLM timeout" in result["error"]


# ── emit_audit ─────────────────────────────────────────────────────────

def test_emit_audit_non_fatal_on_db_error():
    """emit_audit swallows DB errors silently."""
    from kotodama.langgraph_graphs.shosha_agent_loop import emit_audit

    with patch("kotodama.langgraph_graphs.shosha_agent_loop.sync_cursor") as mock_ctx:
        mock_ctx.return_value.__enter__ = MagicMock(side_effect=RuntimeError("db down"))
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result = emit_audit({"ok": True, "latencyMs": 100})

    assert result == {}


def test_emit_audit_inserts_row():
    from kotodama.langgraph_graphs.shosha_agent_loop import emit_audit

    mock_cur = MagicMock()
    with patch("kotodama.langgraph_graphs.shosha_agent_loop.sync_cursor") as mock_ctx:
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        emit_audit({"ok": True, "latencyMs": 200})

    mock_cur.execute.assert_called_once()
    sql_called = mock_cur.execute.call_args[0][0]
    assert "vertex_repo_commit" in sql_called


# ── graph wiring ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_graph_runs_end_to_end():
    """Full graph ainvoke with all external calls mocked."""
    mock_resp = {"content": "WTI bullish.", "model": "qwen3", "latencyMs": 300}

    with (
        patch("kotodama.langgraph_graphs.shosha_agent_loop._rw_query", return_value=[]),
        patch("kotodama.langgraph_graphs.shosha_agent_loop.llm") as mock_llm,
        patch("kotodama.langgraph_graphs.shosha_agent_loop.sync_cursor") as mock_ctx,
    ):
        mock_llm.call_tier.return_value = mock_resp
        mock_llm.LlmError = Exception
        mock_cur = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        from kotodama.langgraph_graphs.shosha_agent_loop import build_graph
        graph = build_graph()
        result = await graph.ainvoke({"prompt": "WTI outlook?", "tier": "reasoning"})

    assert result["ok"] is True
    assert result["content"] == "WTI bullish."
    assert result["model"] == "qwen3"
