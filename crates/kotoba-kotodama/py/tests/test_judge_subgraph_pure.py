"""Pure structural tests for the 4-step judge subgraph.

Topology: START -> sense -> plan -> act -> reflect -> {plan | END}.
Validates each node in isolation + run_judge end-to-end with a mocked LLM.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph", reason="langgraph not installed in this env")
pytest.importorskip("langchain_anthropic", reason="langchain_anthropic not installed")


# --------------------------------------------------------------------- nodes


def test_sense_normalizes_dict_signals_to_json() -> None:
    from kotodama.langgraph_graphs._subgraphs import judge as j

    out = j._sense({"raw_signals": {"a": 1, "b": "two"}})
    assert isinstance(out["signals_json"], str)
    assert '"a": 1' in out["signals_json"]
    assert out["attempt"] == 0


def test_sense_truncates_long_payload() -> None:
    from kotodama.langgraph_graphs._subgraphs import judge as j

    big = "x" * 10_000
    out = j._sense({"raw_signals": big, "truncation_chars": 100})
    assert len(out["signals_json"]) == 100


def test_sense_handles_none() -> None:
    from kotodama.langgraph_graphs._subgraphs import judge as j

    out = j._sense({"raw_signals": None})
    assert out["signals_json"] == "{}"


def test_plan_picks_persona_temperature() -> None:
    from kotodama.langgraph_graphs._subgraphs import judge as j

    cons = j._plan({"persona": "conservative", "attempt": 0})
    aggr = j._plan({"persona": "aggressive", "attempt": 0})
    assert cons["temperature"] < aggr["temperature"]
    # Bumped on retry
    cons_retry = j._plan({"persona": "conservative", "attempt": 1})
    assert cons_retry["temperature"] > cons["temperature"]


def test_plan_temperature_capped_at_1() -> None:
    from kotodama.langgraph_graphs._subgraphs import judge as j

    out = j._plan({"persona": "aggressive", "attempt": 100})
    assert out["temperature"] <= 1.0


def test_reflect_parses_threat_score_key() -> None:
    from kotodama.langgraph_graphs._subgraphs import judge as j

    out = j._reflect({"raw_response": '{"threat_score": 0.42, "summary": "ok"}'})
    assert out["parse_ok"] is True
    assert out["score"] == 0.42
    assert out["summary"] == "ok"


def test_reflect_parses_score_alias_key() -> None:
    from kotodama.langgraph_graphs._subgraphs import judge as j

    out = j._reflect({"raw_response": '{"score": 0.7, "summary": "x"}'})
    assert out["parse_ok"] is True
    assert out["score"] == 0.7


def test_reflect_rejects_out_of_range_score() -> None:
    from kotodama.langgraph_graphs._subgraphs import judge as j

    out = j._reflect({"raw_response": '{"threat_score": 9.0, "summary": "x"}'})
    assert out["parse_ok"] is False


def test_reflect_handles_malformed_response() -> None:
    from kotodama.langgraph_graphs._subgraphs import judge as j

    out = j._reflect({"raw_response": "not json at all"})
    assert out["parse_ok"] is False
    assert out["score"] == 0.5  # fallback
    assert "not json" in out["summary"]


def test_route_after_reflect_loops_when_malformed() -> None:
    from kotodama.langgraph_graphs._subgraphs import judge as j
    from langgraph.graph import END

    assert j._route_after_reflect({"parse_ok": True}) == END
    assert j._route_after_reflect({"parse_ok": False, "attempt": 1, "max_retries": 1}) == "plan"
    assert j._route_after_reflect({"parse_ok": False, "attempt": 2, "max_retries": 1}) == END


# --------------------------------------------------------------- end-to-end


def test_subgraph_compiles_with_4_step_topology() -> None:
    from kotodama.langgraph_graphs._subgraphs import judge as j

    g = j.build_judge_subgraph()
    user_nodes = set(g.get_graph().nodes.keys()) - {"__start__", "__end__"}
    assert user_nodes == {"sense", "plan", "act", "reflect"}


def test_run_judge_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from kotodama.langgraph_graphs._subgraphs import judge as j

    class _Resp:
        content = '{"threat_score": 0.73, "summary": "moderate"}'

    monkeypatch.setattr(
        j, "_llm",
        lambda *a, **kw: type("F", (), {"invoke": lambda self, _: _Resp()})(),
    )
    j._SUBGRAPH = None

    out = j.run_judge(
        persona="conservative",
        subject="Acme Corp",
        signals={"a": 1},
    )
    assert out == {"persona": "conservative", "score": 0.73, "summary": "moderate"}


def test_run_judge_retries_on_malformed_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """First _llm call returns garbage; second call returns valid JSON."""
    from kotodama.langgraph_graphs._subgraphs import judge as j

    calls: list[float] = []

    class _Garbage:
        content = "this is not json"

    class _Good:
        content = '{"threat_score": 0.6, "summary": "ok"}'

    def _fake_llm(temperature: float = 0.2, max_tokens: int = 512):
        calls.append(temperature)
        invoke_returns = _Garbage() if len(calls) == 1 else _Good()
        return type("F", (), {"invoke": lambda self, _: invoke_returns})()

    monkeypatch.setattr(j, "_llm", _fake_llm)
    j._SUBGRAPH = None

    out = j.run_judge(persona="neutral", subject="x", signals={}, max_retries=1)
    assert len(calls) == 2, "should have retried exactly once"
    assert calls[1] > calls[0], "retry should bump temperature"
    assert out["score"] == 0.6
    assert out["summary"] == "ok"


def test_run_judge_falls_back_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    from kotodama.langgraph_graphs._subgraphs import judge as j

    class _Garbage:
        content = "still not json"

    monkeypatch.setattr(
        j, "_llm",
        lambda *a, **kw: type("F", (), {"invoke": lambda self, _: _Garbage()})(),
    )
    j._SUBGRAPH = None

    out = j.run_judge(persona="neutral", subject="x", signals={}, max_retries=1)
    assert out["score"] == 0.5  # fallback
    assert "still not json" in out["summary"]


def test_compintel_judge_node_uses_subgraph(monkeypatch: pytest.MonkeyPatch) -> None:
    """compintel.judge_node must delegate to run_judge."""
    from kotodama import compintel_worker_main as m

    captured: dict = {}

    def fake_run_judge(persona, subject, signals, prompt_suffix=None):
        captured.update(
            persona=persona, subject=subject, signals=signals, prompt_suffix=prompt_suffix
        )
        return {"persona": persona, "score": 0.6, "summary": "ok"}

    import kotodama.langgraph_graphs._subgraphs.judge as j_mod
    monkeypatch.setattr(j_mod, "run_judge", fake_run_judge)

    out = m.judge_node({
        "_judge_persona": "aggressive",
        "competitor_name": "Acme",
        "pricing_signals": "p",
        "product_signals": "pr",
        "hiring_signals": "h",
        "funding_signals": "f",
        "press_signals": "n",
    })
    assert captured["persona"] == "aggressive"
    assert "Acme" in captured["subject"]
    assert captured["signals"]["pricing"] == "p"
    assert out["judges"][0]["score"] == 0.6
