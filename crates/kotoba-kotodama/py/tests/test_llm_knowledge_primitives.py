from kotodama.primitives import llm_knowledge
from kotodama import llm


def _contexts():
    return [
        {
            "title": "Pokémon Pokopia Dream Island domain knowledge",
            "chunk_text": "夢島に行くには、まずフワンテと仲良くなってフワンテのすみかを完成させる。",
        },
        {
            "title": "Pokémon Pokopia Dream Island domain knowledge",
            "chunk_text": "Dream Island の参考画像: https://example.test/dream-island.png",
        },
    ]


def test_answer_returns_error_when_llm_returns_empty(monkeypatch):
    monkeypatch.setattr(
        llm_knowledge.llm,
        "call_tier",
        lambda *_args, **_kwargs: {"content": "", "model": "tier0-general", "latencyMs": 12},
    )

    out = llm_knowledge.answer(
        question="夢島に行くには？",
        contexts=_contexts(),
        citations=["https://example.test/source"],
        tier="fast",
        lang="ja",
    )

    assert out["ok"] is False
    assert out["answer"] == ""
    assert out["error"] == "llm backend returned empty content"
    assert out["errorKind"] == "EmptyLlmContent"
    assert out["model"] == "tier0-general"
    assert out["confidence"] == "error"


def test_answer_returns_error_on_llm_error(monkeypatch):
    def raise_error(*_args, **_kwargs):
        raise llm.LlmError("backend unavailable")

    monkeypatch.setattr(llm_knowledge.llm, "call_tier", raise_error)

    out = llm_knowledge.answer(
        question="夢島に行くには？",
        contexts=_contexts(),
        citations=["https://example.test/source"],
        tier="fast",
        lang="ja",
    )

    assert out["ok"] is False
    assert out["answer"] == ""
    assert out["error"] == "llm backend failed: backend unavailable"
    assert out["errorKind"] == "LlmError"
    assert out["confidence"] == "error"
