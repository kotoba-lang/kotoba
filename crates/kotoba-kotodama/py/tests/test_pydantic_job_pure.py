"""Pure unit tests for pydantic_job.py (ADR-2605080200).

No DB, no network, no Zeebe connection required.

Coverage:
- ZeebeJobInput.from_job()  — parse job.variables into typed model
- ZeebeJobInput.from_dict() — alternate constructor
- ZeebeJobInput extra fields — silently ignored (extra="ignore")
- ZeebeJobInput validation error — bad type raises ValidationError
- ZeebeJobOutput.to_variables() — serialise to plain dict
- ZeebeJobOutput none fields — preserved (exclude_none=False)
- BaseModelState.merge() — immutable update returns new instance
- BaseModelState extra keys — allowed (LangGraph injects keys)
- AnthropicStructuredOutput.from_tool_use() — parse tool input dict
- AnthropicStructuredOutput.safe_parse() — returns None on bad input
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from kotodama.primitives.pydantic_job import (
    AnthropicStructuredOutput,
    BaseModelState,
    ZeebeJobInput,
    ZeebeJobOutput,
)


# ─────────────────────────────────────────────── concrete subclasses ──

class _GrowthInput(ZeebeJobInput):
    actor_did: str
    eta_score: float
    trigger: str = "timer"


class _GrowthOutput(ZeebeJobOutput):
    proposed_did: str
    eta_score: float
    error: str | None = None


class _ProposeState(BaseModelState):
    actor_did: str = ""
    step: int = 0
    done: bool = False


class _ConciseSummary(AnthropicStructuredOutput):
    summary: str
    confidence: float


# ─────────────────────────────────────────────── ZeebeJobInput ──

def test_from_job_parses_variables():
    job = MagicMock()
    job.variables = {"actor_did": "did:web:test.etzhayyim.com", "eta_score": 0.8}
    inp = _GrowthInput.from_job(job)
    assert inp.actor_did == "did:web:test.etzhayyim.com"
    assert inp.eta_score == 0.8
    assert inp.trigger == "timer"  # default


def test_from_job_none_variables_uses_empty():
    job = MagicMock()
    job.variables = None
    with pytest.raises(ValidationError):
        _GrowthInput.from_job(job)


def test_from_job_extra_fields_ignored():
    job = MagicMock()
    job.variables = {"actor_did": "did:web:x.etzhayyim.com", "eta_score": 0.5, "garbage": 999}
    inp = _GrowthInput.from_job(job)
    assert inp.actor_did == "did:web:x.etzhayyim.com"
    assert not hasattr(inp, "garbage")


def test_from_dict_parses_correctly():
    inp = _GrowthInput.from_dict({"actor_did": "did:web:y.etzhayyim.com", "eta_score": 1.0})
    assert inp.eta_score == 1.0


def test_from_dict_type_coercion():
    # strict=False: string "0.5" should coerce to float
    inp = _GrowthInput.from_dict({"actor_did": "did:web:y.etzhayyim.com", "eta_score": "0.5"})
    assert inp.eta_score == 0.5


def test_from_dict_validation_error_on_missing_required():
    with pytest.raises(ValidationError):
        _GrowthInput.from_dict({"eta_score": 0.5})  # actor_did missing


# ─────────────────────────────────────────────── ZeebeJobOutput ──

def test_to_variables_returns_dict():
    out = _GrowthOutput(proposed_did="did:web:new.etzhayyim.com", eta_score=0.91)
    v = out.to_variables()
    assert isinstance(v, dict)
    assert v["proposed_did"] == "did:web:new.etzhayyim.com"
    assert v["eta_score"] == 0.91


def test_to_variables_none_fields_included():
    out = _GrowthOutput(proposed_did="did:web:new.etzhayyim.com", eta_score=0.5, error=None)
    v = out.to_variables()
    assert "error" in v
    assert v["error"] is None


def test_to_variables_mode_json():
    # model_dump(mode="json") must serialise floats as JSON-safe values
    out = _GrowthOutput(proposed_did="did:web:x.etzhayyim.com", eta_score=0.123456789)
    v = out.to_variables()
    assert isinstance(v["eta_score"], float)


# ─────────────────────────────────────────────── BaseModelState ──

def test_merge_returns_new_instance():
    state = _ProposeState(actor_did="did:web:a.etzhayyim.com", step=0)
    updated = state.merge({"step": 1, "done": True})
    assert updated.step == 1
    assert updated.done is True
    # original unchanged
    assert state.step == 0


def test_merge_preserves_unmentioned_fields():
    state = _ProposeState(actor_did="did:web:b.etzhayyim.com", step=3)
    updated = state.merge({"done": True})
    assert updated.actor_did == "did:web:b.etzhayyim.com"
    assert updated.step == 3


def test_extra_keys_allowed_for_langgraph():
    state = _ProposeState.model_validate(
        {"actor_did": "did:web:c.etzhayyim.com", "langgraph_injected": "value"}
    )
    assert state.actor_did == "did:web:c.etzhayyim.com"


# ─────────────────────────────────────────────── AnthropicStructuredOutput ──

def test_from_tool_use_parses():
    out = _ConciseSummary.from_tool_use({"summary": "brief", "confidence": 0.95})
    assert out.summary == "brief"
    assert out.confidence == 0.95


def test_from_tool_use_extra_ignored():
    out = _ConciseSummary.from_tool_use(
        {"summary": "x", "confidence": 0.5, "thinking": "internal"}
    )
    assert out.summary == "x"
    assert not hasattr(out, "thinking")


def test_safe_parse_returns_none_on_bad_input():
    result = _ConciseSummary.safe_parse({"confidence": "not-a-float"})
    assert result is None


def test_safe_parse_returns_default_on_error():
    default = _ConciseSummary(summary="fallback", confidence=0.0)
    result = _ConciseSummary.safe_parse({}, default=default)
    assert result is default


def test_safe_parse_succeeds_on_valid_input():
    result = _ConciseSummary.safe_parse({"summary": "ok", "confidence": 0.7})
    assert result is not None
    assert result.confidence == 0.7
