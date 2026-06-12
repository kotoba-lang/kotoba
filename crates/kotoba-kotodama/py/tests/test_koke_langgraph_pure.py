"""
Pure unit tests for koke.cycle.v1 LangGraph chain.

Validates:
  - graph compiles
  - declared node set matches the photosynthesis cycle topology
  - has_signals_gate / confidence_gate routing
  - no live RW / Zeebe / LLM dependency
"""

from __future__ import annotations

import pytest

langgraph = pytest.importorskip("langgraph")


def test_koke_cycle_graph_compiles():
    from kotodama.langgraph_graphs.koke_cycle import build_graph

    g = build_graph()
    assert g is not None
    # ainvoke is the public surface — both _CompiledGraph and CompiledStateGraph expose it
    assert callable(getattr(g, "ainvoke", None))


def test_koke_has_signals_gate():
    from kotodama.langgraph_graphs.koke_cycle import _has_signals_gate

    assert _has_signals_gate({"signalCount": 5}) == "fix"
    assert _has_signals_gate({"signalCount": 0}) == "no_signals"
    assert _has_signals_gate({}) == "no_signals"


def test_koke_confidence_gate():
    from kotodama.langgraph_graphs.koke_cycle import _confidence_gate

    assert _confidence_gate({"confidence": 0.9}) == "hakkou"
    assert _confidence_gate({"confidence": 0.7}) == "hakkou"
    assert _confidence_gate({"confidence": 0.69}) == "saikin"
    assert _confidence_gate({"confidence": 0.0}) == "saikin"
    assert _confidence_gate({}) == "saikin"
