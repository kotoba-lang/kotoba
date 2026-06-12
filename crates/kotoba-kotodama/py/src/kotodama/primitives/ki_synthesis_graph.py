"""
ki.synthesize LangGraph pipeline — ADR-2605071200.

3-node StateGraph:
  parse     — classify input kind and extract content summary
  synthesize — primary LLM call: structured knowledge artifact generation
  refine    — conditional second pass when confidence < REFINE_THRESHOLD

Registered as "ki.synthesize.v1" in langgraph_registry at import time.
ki_worker_main imports this module to wire it into task_synthesize.

Graph ID: "ki.synthesize.v1"
"""

from __future__ import annotations

import os
import time
from typing import Any, TypedDict

from kotodama import llm
from kotodama.primitives import langgraph_registry

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover
    END = "__end__"
    StateGraph = None  # type: ignore[assignment]

REFINE_THRESHOLD = float(os.environ.get("KI_REFINE_THRESHOLD", "0.7"))
CONFIDENCE_CUTOFF = float(os.environ.get("KI_CONFIDENCE_CUTOFF", "0.6"))

ARTIFACT_KINDS = {"insight", "pattern", "relation", "fact", "model"}


class SynthesisState(TypedDict, total=False):
    # Inputs
    absorbId: str
    inputKind: str
    content: str
    # After parse
    contentSummary: str
    classifiedKind: str
    # After synthesize
    title: str
    synthesis: str
    confidence: float
    artifactKind: str
    keyPoints: list[str]
    # After refine
    refined: bool
    # Error
    error: str
    # Timing
    latencyMs: int


# ─── node: parse ──────────────────────────────────────────────────────────────


def _parse_node(state: SynthesisState) -> SynthesisState:
    """Classify input kind and create a focused content summary."""
    content = state.get("content", "")
    input_kind = state.get("inputKind", "text")

    if not content:
        return {**state, "error": "empty content", "contentSummary": "", "classifiedKind": input_kind}

    # Lightweight classification without LLM — check content signals
    c = content.lower()
    if input_kind == "url" or c.startswith("http"):
        classified = "url"
    elif any(k in c for k in ["def ", "class ", "import ", "function ", "SELECT ", "INSERT "]):
        classified = "code"
    elif any(k in c for k in ["\n-", "\n*", "1.", "2.", "・"]):
        classified = "structured"
    else:
        classified = "text"

    return {
        **state,
        "classifiedKind": classified,
        "contentSummary": content[:800].strip(),
    }


# ─── node: synthesize ─────────────────────────────────────────────────────────


def _synthesize_node(state: SynthesisState) -> SynthesisState:
    """Primary LLM call: generate structured knowledge artifact."""
    if state.get("error"):
        return state

    started = time.monotonic()
    content = state.get("contentSummary") or state.get("content", "")
    input_kind = state.get("classifiedKind") or state.get("inputKind", "text")

    system = (
        "You are ki — the vascular synthesis layer of an artificial organism. "
        "Synthesize the input into a structured knowledge artifact. "
        "Respond ONLY with a JSON object using these keys: "
        "title (string), summary (string), keyPoints (array of strings), "
        "confidence (float 0.0-1.0), "
        f"artifactKind (one of: {', '.join(sorted(ARTIFACT_KINDS))})."
    )
    user = f"Input kind: {input_kind}\n\n{content[:2000]}"

    try:
        result = llm.call_tier("mid", system=system, user=user, max_tokens=500)
    except llm.LlmError as exc:
        return {
            **state,
            "error": f"llm failed: {exc}",
            "synthesis": "",
            "confidence": 0.0,
            "artifactKind": "insight",
            "keyPoints": [],
            "latencyMs": int((time.monotonic() - started) * 1000),
        }

    raw = (result.get("content") or "").strip()
    latency = int(result.get("latencyMs") or (time.monotonic() - started) * 1000)

    import json
    try:
        parsed = json.loads(raw)
        synthesis = str(parsed.get("summary", raw[:200]))
        confidence = float(parsed.get("confidence", 0.5))
        artifact_kind = str(parsed.get("artifactKind", "insight"))
        if artifact_kind not in ARTIFACT_KINDS:
            artifact_kind = "insight"
        key_points = list(parsed.get("keyPoints", []))
        title = str(parsed.get("title", ""))
    except (json.JSONDecodeError, ValueError, TypeError):
        synthesis = raw[:200]
        confidence = 0.5
        artifact_kind = "insight"
        key_points = []
        title = ""

    return {
        **state,
        "title": title,
        "synthesis": synthesis,
        "confidence": confidence,
        "artifactKind": artifact_kind,
        "keyPoints": key_points,
        "latencyMs": latency,
        "refined": False,
    }


# ─── node: refine ─────────────────────────────────────────────────────────────


def _refine_node(state: SynthesisState) -> SynthesisState:
    """Second LLM pass to improve low-confidence artifacts."""
    if state.get("error"):
        return state

    started = time.monotonic()
    prior_synthesis = state.get("synthesis", "")
    content = state.get("contentSummary") or state.get("content", "")
    artifact_kind = state.get("artifactKind", "insight")

    system = (
        "You are ki — improving a low-confidence knowledge artifact. "
        "Given the original synthesis and source content, produce an improved version. "
        "Respond ONLY with JSON: "
        "summary (string), confidence (float 0.0-1.0), "
        "keyPoints (array of strings up to 5)."
    )
    user = (
        f"Prior synthesis (confidence={state.get('confidence', 0):.2f}):\n{prior_synthesis}\n\n"
        f"Source content:\n{content[:1500]}"
    )

    try:
        result = llm.call_tier("mid", system=system, user=user, max_tokens=300)
    except llm.LlmError:
        return {**state, "refined": False}

    raw = (result.get("content") or "").strip()

    import json
    try:
        parsed = json.loads(raw)
        new_synthesis = str(parsed.get("summary", prior_synthesis))
        new_confidence = float(parsed.get("confidence", state.get("confidence", 0.5)))
        new_key_points = list(parsed.get("keyPoints", state.get("keyPoints", [])))
    except (json.JSONDecodeError, ValueError, TypeError):
        return {**state, "refined": False}

    # Only accept refinement if it improved confidence
    if new_confidence > (state.get("confidence") or 0):
        return {
            **state,
            "synthesis": new_synthesis,
            "confidence": new_confidence,
            "keyPoints": new_key_points,
            "refined": True,
            "latencyMs": (state.get("latencyMs") or 0) + int((time.monotonic() - started) * 1000),
        }
    return {**state, "refined": False}


# ─── routing ──────────────────────────────────────────────────────────────────


def _should_refine(state: SynthesisState) -> str:
    """Route to 'refine' if confidence is low but above absolute cutoff."""
    if state.get("error"):
        return END
    confidence = state.get("confidence") or 0.0
    if CONFIDENCE_CUTOFF <= confidence < REFINE_THRESHOLD:
        return "refine"
    return END


# ─── graph builder ────────────────────────────────────────────────────────────


def _build_graph():
    if StateGraph is None:
        return None

    graph = StateGraph(SynthesisState)
    graph.add_node("parse", _parse_node)
    graph.add_node("synthesize", _synthesize_node)
    graph.add_node("refine", _refine_node)

    graph.set_entry_point("parse")
    graph.add_edge("parse", "synthesize")
    graph.add_conditional_edges("synthesize", _should_refine, {"refine": "refine", END: END})
    graph.add_edge("refine", END)

    return graph.compile()


_GRAPH = None


def synthesize(
    absorbId: str = "",
    inputKind: str = "text",
    content: str = "",
) -> dict[str, Any]:
    """Run the ki synthesis LangGraph pipeline and return the artifact fields."""
    global _GRAPH

    state: SynthesisState = {
        "absorbId": absorbId,
        "inputKind": inputKind,
        "content": content,
    }

    if _GRAPH is None:
        _GRAPH = _build_graph()

    if _GRAPH is not None and hasattr(_GRAPH, "invoke"):
        result: SynthesisState = _GRAPH.invoke(state)
    else:
        # Fallback path (LangGraph unavailable): run nodes sequentially
        result = _refine_node(_synthesize_node(_parse_node(state))) if (
            not _synthesize_node(_parse_node(state)).get("error")
            and _should_refine(_synthesize_node(_parse_node(state))) == "refine"
        ) else _synthesize_node(_parse_node(state))

    return {
        "synthesis": result.get("synthesis", ""),
        "title": result.get("title", ""),
        "confidence": result.get("confidence", 0.5),
        "artifactKind": result.get("artifactKind", "insight"),
        "keyPoints": result.get("keyPoints", []),
        "refined": bool(result.get("refined", False)),
        "latencyMs": result.get("latencyMs", 0),
        "error": result.get("error", ""),
    }


# Register with the generic.langgraph.run dispatcher
if StateGraph is not None:
    langgraph_registry.register("ki.synthesize.v1", _build_graph())
