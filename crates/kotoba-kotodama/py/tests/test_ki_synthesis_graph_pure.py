"""Pure-logic tests for ki_synthesis_graph LangGraph nodes (no LLM or DB)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


# ─── _parse_node ──────────────────────────────────────────────────────────────


def test_parse_empty_content():
    from kotodama.primitives.ki_synthesis_graph import _parse_node

    state = {"content": "", "inputKind": "text"}
    out = _parse_node(state)
    assert out["error"] == "empty content"
    assert out["contentSummary"] == ""


def test_parse_classifies_url():
    from kotodama.primitives.ki_synthesis_graph import _parse_node

    state = {"content": "https://example.com/article", "inputKind": "text"}
    out = _parse_node(state)
    assert out["classifiedKind"] == "url"
    assert "example.com" in out["contentSummary"]


def test_parse_classifies_code():
    from kotodama.primitives.ki_synthesis_graph import _parse_node

    state = {"content": "def compute_eta(flow, total):\n    return flow / total", "inputKind": "text"}
    out = _parse_node(state)
    assert out["classifiedKind"] == "code"


def test_parse_classifies_structured():
    from kotodama.primitives.ki_synthesis_graph import _parse_node

    state = {"content": "Summary:\n- point one\n- point two\n* point three", "inputKind": "text"}
    out = _parse_node(state)
    assert out["classifiedKind"] == "structured"


def test_parse_classifies_text():
    from kotodama.primitives.ki_synthesis_graph import _parse_node

    state = {"content": "The organism demonstrated adaptive behaviour.", "inputKind": "text"}
    out = _parse_node(state)
    assert out["classifiedKind"] == "text"


def test_parse_respects_input_kind_url():
    from kotodama.primitives.ki_synthesis_graph import _parse_node

    state = {"content": "plain sentence here", "inputKind": "url"}
    out = _parse_node(state)
    assert out["classifiedKind"] == "url"


def test_parse_truncates_long_content():
    from kotodama.primitives.ki_synthesis_graph import _parse_node

    long = "x" * 1000
    state = {"content": long, "inputKind": "text"}
    out = _parse_node(state)
    assert len(out["contentSummary"]) <= 800


# ─── _synthesize_node ─────────────────────────────────────────────────────────


def test_synthesize_skips_on_error():
    from kotodama.primitives.ki_synthesis_graph import _synthesize_node

    state = {"error": "upstream fail", "content": "hello"}
    out = _synthesize_node(state)
    assert out["error"] == "upstream fail"
    assert "synthesis" not in out


def test_synthesize_valid_json_response():
    import json

    mock_llm = MagicMock(return_value={
        "content": json.dumps({
            "title": "Test Title",
            "summary": "The key insight is X.",
            "confidence": 0.88,
            "artifactKind": "insight",
            "keyPoints": ["point A", "point B"],
        }),
        "latencyMs": 150,
    })

    with patch("kotodama.primitives.ki_synthesis_graph.llm.call_tier", mock_llm):
        from kotodama.primitives.ki_synthesis_graph import _synthesize_node

        state = {"content": "sample", "contentSummary": "sample", "classifiedKind": "text"}
        out = _synthesize_node(state)

    assert out["synthesis"] == "The key insight is X."
    assert out["title"] == "Test Title"
    assert out["confidence"] == 0.88
    assert out["artifactKind"] == "insight"
    assert out["keyPoints"] == ["point A", "point B"]
    assert out["refined"] is False


def test_synthesize_invalid_json_falls_back():
    mock_llm = MagicMock(return_value={"content": "not valid json here", "latencyMs": 50})

    with patch("kotodama.primitives.ki_synthesis_graph.llm.call_tier", mock_llm):
        from kotodama.primitives.ki_synthesis_graph import _synthesize_node

        state = {"content": "sample", "contentSummary": "sample", "classifiedKind": "text"}
        out = _synthesize_node(state)

    assert out["confidence"] == 0.5
    assert out["artifactKind"] == "insight"
    assert out["synthesis"]


def test_synthesize_unknown_artifact_kind_defaults_to_insight():
    import json

    mock_llm = MagicMock(return_value={
        "content": json.dumps({"summary": "s", "confidence": 0.7, "artifactKind": "unknown_kind", "keyPoints": []}),
    })

    with patch("kotodama.primitives.ki_synthesis_graph.llm.call_tier", mock_llm):
        from kotodama.primitives.ki_synthesis_graph import _synthesize_node

        state = {"contentSummary": "text"}
        out = _synthesize_node(state)

    assert out["artifactKind"] == "insight"


def test_synthesize_llm_error_propagates():
    from kotodama.primitives.ki_synthesis_graph import _synthesize_node
    from kotodama import llm

    with patch("kotodama.primitives.ki_synthesis_graph.llm.call_tier", side_effect=llm.LlmError("timeout")):
        state = {"contentSummary": "hello"}
        out = _synthesize_node(state)

    assert "error" in out
    assert "llm failed" in out["error"]
    assert out["confidence"] == 0.0


# ─── _refine_node ─────────────────────────────────────────────────────────────


def test_refine_skips_on_error():
    from kotodama.primitives.ki_synthesis_graph import _refine_node

    state = {"error": "bad", "synthesis": "x"}
    out = _refine_node(state)
    assert out["error"] == "bad"


def test_refine_improves_confidence():
    import json

    mock_llm = MagicMock(return_value={
        "content": json.dumps({
            "summary": "improved synthesis text",
            "confidence": 0.82,
            "keyPoints": ["better point"],
        }),
    })

    with patch("kotodama.primitives.ki_synthesis_graph.llm.call_tier", mock_llm):
        from kotodama.primitives.ki_synthesis_graph import _refine_node

        state = {
            "synthesis": "initial synthesis",
            "confidence": 0.65,
            "contentSummary": "content",
            "artifactKind": "insight",
            "keyPoints": [],
        }
        out = _refine_node(state)

    assert out["refined"] is True
    assert out["synthesis"] == "improved synthesis text"
    assert out["confidence"] == 0.82
    assert out["keyPoints"] == ["better point"]


def test_refine_rejects_lower_confidence():
    import json

    mock_llm = MagicMock(return_value={
        "content": json.dumps({"summary": "worse", "confidence": 0.6, "keyPoints": []}),
    })

    with patch("kotodama.primitives.ki_synthesis_graph.llm.call_tier", mock_llm):
        from kotodama.primitives.ki_synthesis_graph import _refine_node

        state = {"synthesis": "original", "confidence": 0.65, "contentSummary": "c", "keyPoints": []}
        out = _refine_node(state)

    assert out["refined"] is False
    assert out["synthesis"] == "original"
    assert out["confidence"] == 0.65


def test_refine_llm_error_returns_unrefined():
    from kotodama.primitives.ki_synthesis_graph import _refine_node
    from kotodama import llm

    with patch("kotodama.primitives.ki_synthesis_graph.llm.call_tier", side_effect=llm.LlmError("err")):
        state = {"synthesis": "s", "confidence": 0.65, "contentSummary": "c", "keyPoints": []}
        out = _refine_node(state)

    assert out["refined"] is False


# ─── _should_refine ───────────────────────────────────────────────────────────


def test_should_refine_routes_to_refine():
    from kotodama.primitives.ki_synthesis_graph import _should_refine, CONFIDENCE_CUTOFF, REFINE_THRESHOLD

    # Exactly in the refine window
    mid = (CONFIDENCE_CUTOFF + REFINE_THRESHOLD) / 2
    state = {"confidence": mid}
    assert _should_refine(state) == "refine"


def test_should_refine_high_confidence_goes_to_end():
    from kotodama.primitives.ki_synthesis_graph import _should_refine, REFINE_THRESHOLD, END

    state = {"confidence": REFINE_THRESHOLD + 0.05}
    assert _should_refine(state) == END


def test_should_refine_low_confidence_goes_to_end():
    from kotodama.primitives.ki_synthesis_graph import _should_refine, CONFIDENCE_CUTOFF, END

    state = {"confidence": CONFIDENCE_CUTOFF - 0.05}
    assert _should_refine(state) == END


def test_should_refine_error_state_goes_to_end():
    from kotodama.primitives.ki_synthesis_graph import _should_refine, END

    state = {"error": "something failed", "confidence": 0.65}
    assert _should_refine(state) == END


# ─── synthesize (full pipeline, mocked LLM) ───────────────────────────────────


def test_synthesize_pipeline_returns_fields():
    import json

    mock_llm = MagicMock(return_value={
        "content": json.dumps({
            "title": "T",
            "summary": "Full pipeline output.",
            "confidence": 0.91,
            "artifactKind": "fact",
            "keyPoints": ["k1"],
        }),
    })

    with patch("kotodama.primitives.ki_synthesis_graph.llm.call_tier", mock_llm):
        from kotodama.primitives.ki_synthesis_graph import synthesize

        result = synthesize(content="hello world knowledge")

    assert result["synthesis"] == "Full pipeline output."
    assert result["confidence"] == 0.91
    assert result["artifactKind"] == "fact"
    assert result["error"] == ""
