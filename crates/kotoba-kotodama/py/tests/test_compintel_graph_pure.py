"""Pure structural tests for compintel LangGraph (no LLM, no Zeebe, no DB).

Validates:
  - Graph compiles
  - dispatch_judges returns N Send objects
  - reduce_judges computes median + closest summary
"""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph", reason="langgraph not installed in this env")
pytest.importorskip("langchain_anthropic", reason="langchain_anthropic not installed")


def test_graph_compiles() -> None:
    from kotodama import compintel_worker_main as m

    assert m._GRAPH is not None
    nodes = set(m._GRAPH.get_graph().nodes.keys())
    for required in (
        "fetch_signals", "analyze_pricing", "analyze_product", "analyze_hiring",
        "collect_signals", "judge_node", "reduce_judges", "store_snapshot",
    ):
        assert required in nodes, f"missing node: {required}"


def test_dispatch_judges_emits_one_send_per_persona() -> None:
    from kotodama import compintel_worker_main as m

    state = {"competitor_name": "Acme", "pricing_signals": "x"}
    sends = m.dispatch_judges(state)  # type: ignore[arg-type]
    assert len(sends) == len(m._JUDGE_PERSONAS)
    assert {s.node for s in sends} == {"judge_node"}
    personas = sorted(s.arg["_judge_persona"] for s in sends)
    assert personas == sorted(m._JUDGE_PERSONAS)


def test_reduce_judges_picks_median() -> None:
    from kotodama import compintel_worker_main as m

    state = {
        "competitor_name": "Acme",
        "judges": [
            {"persona": "conservative", "score": 0.20, "summary": "cons"},
            {"persona": "neutral", "score": 0.55, "summary": "neu"},
            {"persona": "aggressive", "score": 0.90, "summary": "agg"},
        ],
    }
    out = m.reduce_judges(state)  # type: ignore[arg-type]
    assert out["threat_score"] == 0.55
    assert out["latest_summary"] == "neu"


def test_reduce_judges_handles_empty() -> None:
    from kotodama import compintel_worker_main as m

    out = m.reduce_judges({"competitor_name": "Acme", "judges": []})  # type: ignore[arg-type]
    assert out["threat_score"] == 0.5
    assert out["latest_summary"] == ""
