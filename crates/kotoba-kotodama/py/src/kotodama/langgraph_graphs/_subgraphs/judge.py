"""Reusable judge subgraph (von Neumann minimax assessor).

ADR-2605080000 §6-Layer composition. 4-step Pregel BSP:

  START -> sense -> plan -> act -> reflect -> [retry act | END]

  sense    — normalize input signals (dict | str | None) into a bounded JSON string.
  plan     — pick temperature / max_tokens / criteria from persona.
  act      — invoke LLM with planned params; record raw response + attempt.
  reflect  — parse JSON, validate score range, set parse_ok. On malformed
             output and attempt < max_retries, loop back to act with bumped
             temperature; otherwise emit fallback (score=0.5).

Public API:
  build_judge_subgraph()  — compile the StateGraph.
  run_judge(...)          — sync wrapper, returns {persona, score, summary}.
  arun_judge(...)         — async wrapper, same shape.
  JudgeInput / JudgeOutput — TypedDict aliases for static typing.
"""

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

try:
    from langchain_anthropic import ChatAnthropic
    from langgraph.graph import END, START, StateGraph
    _LG_OK = True
except ImportError:  # pragma: no cover — runtime deps
    _LG_OK = False
    ChatAnthropic = object  # type: ignore[assignment,misc]
    StateGraph = object  # type: ignore[assignment,misc]
    START = "__start__"  # type: ignore[assignment]
    END = "__end__"  # type: ignore[assignment]

from kotodama.llm import resolve_model_id

LOG = logging.getLogger(__name__)


class JudgeInput(TypedDict, total=False):
    # input contract
    persona: str
    subject: str
    raw_signals: Any           # dict | str | list | None — sense will normalize
    prompt_suffix: str
    truncation_chars: int      # default 2000
    max_retries: int           # default 1 (act runs at most twice)
    # sense
    signals_json: str
    # plan
    temperature: float
    max_tokens: int
    # act
    raw_response: str
    attempt: int
    # reflect
    score: float
    summary: str
    parse_ok: bool


JudgeOutput = JudgeInput


_DEFAULT_PROMPT_SUFFIX = (
    'Respond with JSON only: {"threat_score": 0.0-1.0, "summary": "1-2 sentence assessment"}'
)
_DEFAULT_TRUNCATION = 2000
_DEFAULT_MAX_RETRIES = 1

# Persona → (base_temperature, max_tokens). Bumped temperature on retry to
# break out of stuck malformed-JSON loops.
_PERSONA_PLAN: dict[str, tuple[float, int]] = {
    "conservative": (0.10, 512),
    "neutral":      (0.20, 512),
    "aggressive":   (0.40, 512),
}
_DEFAULT_PLAN: tuple[float, int] = (0.20, 512)


def _llm(temperature: float = 0.2, max_tokens: int = 512) -> Any:
    return ChatAnthropic(
        model=resolve_model_id("general"),
        temperature=temperature,
        max_tokens=max_tokens,
    )


# ---------------------------------------------------------------------------
# Pregel nodes
# ---------------------------------------------------------------------------

def _sense(state: JudgeInput) -> dict[str, Any]:
    """Normalize raw_signals → bounded JSON string + carry persona/subject."""
    raw = state.get("raw_signals")
    truncate = int(state.get("truncation_chars", _DEFAULT_TRUNCATION))
    if raw is None:
        signals_json = "{}"
    elif isinstance(raw, str):
        signals_json = raw
    else:
        try:
            signals_json = json.dumps(raw, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            signals_json = str(raw)
    if len(signals_json) > truncate:
        signals_json = signals_json[:truncate]
    return {"signals_json": signals_json, "attempt": 0}


def _plan(state: JudgeInput) -> dict[str, Any]:
    """Persona-aware temperature/max_tokens selection."""
    persona = state.get("persona", "neutral")
    base_temp, max_toks = _PERSONA_PLAN.get(persona, _DEFAULT_PLAN)
    # On retry, bump temperature one step to escape malformed-JSON loops.
    attempt = int(state.get("attempt", 0))
    temperature = round(base_temp + 0.1 * attempt, 2)
    return {"temperature": min(temperature, 1.0), "max_tokens": max_toks}


def _act(state: JudgeInput) -> dict[str, Any]:
    """Invoke LLM with the persona prompt + planned params."""
    persona = state.get("persona", "neutral")
    subject = state.get("subject", "the subject")
    signals = state.get("signals_json", "{}")
    suffix = state.get("prompt_suffix") or _DEFAULT_PROMPT_SUFFIX
    temperature = float(state.get("temperature", _DEFAULT_PLAN[0]))
    max_tokens = int(state.get("max_tokens", _DEFAULT_PLAN[1]))
    prompt = (
        f"You are a {persona} analyst.\n"
        f"Assess: {subject}\n"
        f"Signals:\n{signals}\n\n"
        f"{suffix}"
    )
    resp = _llm(temperature=temperature, max_tokens=max_tokens).invoke(prompt)
    raw = str(getattr(resp, "content", resp)).strip()
    return {"raw_response": raw, "attempt": int(state.get("attempt", 0)) + 1}


def _reflect(state: JudgeInput) -> dict[str, Any]:
    """Parse JSON, validate score, set parse_ok. Fallback summary = raw[:200]."""
    raw = str(state.get("raw_response", "")).strip()
    score: float = 0.5
    summary: str = raw[:200]
    parse_ok = False
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if 0 <= start < end:
            parsed = json.loads(raw[start:end])
            if "threat_score" in parsed:
                score = float(parsed["threat_score"])
            elif "score" in parsed:
                score = float(parsed["score"])
            else:
                raise ValueError("no score key")
            if not (0.0 <= score <= 1.0):
                raise ValueError(f"score out of range: {score}")
            summary = str(parsed.get("summary", summary))
            parse_ok = True
    except Exception as exc:
        LOG.debug("judge reflect parse failed (attempt=%s): %s", state.get("attempt"), exc)
    return {"score": round(score, 3), "summary": summary, "parse_ok": parse_ok}


def _route_after_reflect(state: JudgeInput) -> str:
    """Loop back to act on malformed output, up to max_retries."""
    if state.get("parse_ok"):
        return END
    attempt = int(state.get("attempt", 0))
    max_retries = int(state.get("max_retries", _DEFAULT_MAX_RETRIES))
    if attempt <= max_retries:
        return "plan"  # re-plan with bumped temperature, then re-act
    return END


# ---------------------------------------------------------------------------
# Subgraph builder + invocation wrappers
# ---------------------------------------------------------------------------

def build_judge_subgraph() -> Any:
    """Compile the 4-step judge StateGraph (sense → plan → act → reflect)."""
    if not _LG_OK:  # pragma: no cover
        raise RuntimeError("langgraph not installed")
    g: StateGraph = StateGraph(JudgeInput)
    g.add_node("sense", _sense)
    g.add_node("plan", _plan)
    g.add_node("act", _act)
    g.add_node("reflect", _reflect)
    g.add_edge(START, "sense")
    g.add_edge("sense", "plan")
    g.add_edge("plan", "act")
    g.add_edge("act", "reflect")
    g.add_conditional_edges("reflect", _route_after_reflect, [END, "plan"])
    return g.compile()


_SUBGRAPH: Any | None = None


def _get_subgraph() -> Any:
    global _SUBGRAPH
    if _SUBGRAPH is None:
        _SUBGRAPH = build_judge_subgraph()
    return _SUBGRAPH


def _build_input(
    persona: str,
    subject: str,
    signals: dict[str, Any] | str | None,
    prompt_suffix: str | None,
    *,
    max_retries: int | None = None,
    truncation_chars: int | None = None,
) -> JudgeInput:
    inp: JudgeInput = {
        "persona": persona,
        "subject": subject,
        "raw_signals": signals,
    }
    if prompt_suffix:
        inp["prompt_suffix"] = prompt_suffix
    if max_retries is not None:
        inp["max_retries"] = max_retries
    if truncation_chars is not None:
        inp["truncation_chars"] = truncation_chars
    return inp


def _shape_output(persona: str, out: dict[str, Any]) -> dict[str, Any]:
    return {
        "persona": persona,
        "score": float(out.get("score", 0.5)),
        "summary": str(out.get("summary", "")),
    }


def run_judge(
    persona: str,
    subject: str,
    signals: dict[str, Any] | str | None,
    *,
    prompt_suffix: str | None = None,
    max_retries: int | None = None,
    truncation_chars: int | None = None,
) -> dict[str, Any]:
    """Sync wrapper. Returns {persona, score, summary}."""
    out = _get_subgraph().invoke(
        _build_input(persona, subject, signals, prompt_suffix,
                     max_retries=max_retries, truncation_chars=truncation_chars)
    )
    return _shape_output(persona, out)


async def arun_judge(
    persona: str,
    subject: str,
    signals: dict[str, Any] | str | None,
    *,
    prompt_suffix: str | None = None,
    max_retries: int | None = None,
    truncation_chars: int | None = None,
) -> dict[str, Any]:
    """Async variant of `run_judge`. Same return shape."""
    out = await _get_subgraph().ainvoke(
        _build_input(persona, subject, signals, prompt_suffix,
                     max_retries=max_retries, truncation_chars=truncation_chars)
    )
    return _shape_output(persona, out)
