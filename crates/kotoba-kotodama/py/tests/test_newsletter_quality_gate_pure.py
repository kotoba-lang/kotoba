"""Pure tests for newsletter quality_gate subgraph delegation."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("langgraph", reason="langgraph not installed")
pytest.importorskip("langchain_anthropic", reason="langchain_anthropic not installed")


def test_quality_gate_empty_body_short_circuits() -> None:
    from kotodama import newsletter_worker_main as m

    out = asyncio.run(m.node_quality_gate({"body_html": "", "ranked_signals": []}))
    assert out["quality_score"] == 0.0
    assert out["retry_count"] == 99


def test_quality_gate_delegates_to_judge_subgraph(monkeypatch: pytest.MonkeyPatch) -> None:
    from kotodama import newsletter_worker_main as m

    captured: dict = {}

    async def fake_arun_judge(persona, subject, signals, prompt_suffix=None):
        captured["persona"] = persona
        captured["subject"] = subject
        captured["signals"] = signals
        captured["prompt_suffix"] = prompt_suffix
        return {"persona": persona, "score": 0.82, "summary": "good"}

    import kotodama.langgraph_graphs._subgraphs.judge as j_mod
    monkeypatch.setattr(j_mod, "arun_judge", fake_arun_judge)

    state = {
        "body_html": "<p>hello</p>" * 50,
        "ranked_signals": [{"i": 1}, {"i": 2}],
        "subject_line": "Test subject",
        "topic": "AI agents",
        "cohort_name": "engineers",
    }
    out = asyncio.run(m.node_quality_gate(state))
    assert out == {"quality_score": 0.82}
    assert captured["persona"] == "newsletter editor"
    assert "Test subject" in captured["subject"]
    assert captured["signals"]["topic"] == "AI agents"
    assert "engagement" in captured["prompt_suffix"]
