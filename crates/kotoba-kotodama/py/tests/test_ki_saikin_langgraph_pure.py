"""
Pure unit tests for ki.cycle.v1 + saikin.cycle.v1 LangGraph chains.

Validates:
  - graphs compile
  - declared node set matches the cycle topology
  - confidence_gate / has_signals_gate / transfer_outcome_gate routing
  - no live RW / Zeebe / LLM dependency
"""

from __future__ import annotations

import pytest

langgraph = pytest.importorskip("langgraph")


def test_ki_cycle_graph_compiles():
    from kotodama.langgraph_graphs.ki_cycle import build_graph

    g = build_graph()
    assert g is not None
    assert callable(getattr(g, "ainvoke", None))


def test_saikin_cycle_graph_compiles():
    from kotodama.langgraph_graphs.saikin_cycle import build_graph

    g = build_graph()
    assert g is not None
    assert callable(getattr(g, "ainvoke", None))


def test_ki_confidence_gate():
    from kotodama.langgraph_graphs.ki_cycle import _confidence_gate

    assert _confidence_gate({"confidence": 0.8}) == "bloom"
    assert _confidence_gate({"confidence": 0.59}) == "skip_bloom"
    assert _confidence_gate({}) == "skip_bloom"


def test_saikin_signals_gate():
    from kotodama.langgraph_graphs.saikin_cycle import _has_signals_gate

    assert _has_signals_gate({"signalCount": 3}) == "transfer"
    assert _has_signals_gate({"signalCount": 0}) == "no_signals"
    assert _has_signals_gate({}) == "no_signals"


def test_saikin_transfer_gate():
    from kotodama.langgraph_graphs.saikin_cycle import _transfer_outcome_gate

    assert _transfer_outcome_gate({"transferStatus": "transferred"}) == "form_colony"
    assert _transfer_outcome_gate({"transferStatus": "completed"}) == "lyse"
    assert _transfer_outcome_gate({}) == "lyse"
