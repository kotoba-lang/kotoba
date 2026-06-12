"""pregel.py — Python LangGraph topology for the ameno agent loop.

Path B of ADR-2605191229. Same shape as the TS daemon graph:
  START
   ├ (activeInference?) → surprise_eval → generate
   │                      no             → generate
   ├ generate
   ├ decide_after_generate
   │   ├ <tool> found AND iter<max → execute_tool → generate (loop)
   │   ├ maxIterations > 0          → critic
   │   └ else                        → finalize
   ├ critic → cond:revise/finalize
   ├ revise → critic
   ├ finalize (tool markup strip)
   ├ (activeInference?) → predict_next → END
   │                       no            → END
   └ END

Authoritative ADR: 90-docs/adr/2605191257-ameno-daemon-path-b-kotodama-python.md
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import AsyncIterator
from operator import add
from typing import Annotated, Any, Awaitable, Callable, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver

from .file_checkpointer import FileCheckpointer
from .ollama_stream import GenerationStats, runtime_generate
from .tools import (
    ParsedToolCall,
    execute_tool_call,
    format_tool_history,
    format_tools_for_prompt,
    parse_tool_calls,
    strip_tool_markup,
)


ChatMessage = dict[str, str]

GraphChunk = dict[str, Any]  # see emitter helpers below

GraphPhase = Literal[
    "surprise_eval", "generate", "execute_tool", "critique", "revise", "finalize", "predict_next"
]

# ── State ────────────────────────────────────────────────────────────────


class AmenoState(TypedDict, total=False):
    """LangGraph Pregel state for the ameno agent loop.

    `messages` uses `operator.add` as reducer so node returns of the form
    `{"messages": [<new>]}` append rather than overwrite (parity with
    the TS daemon's Annotation.reducer = a.concat(b)).
    """

    messages: Annotated[list[ChatMessage], add]
    draft: str
    critique: dict[str, Any] | None
    iteration: int
    max_iterations: int
    prediction: str
    surprise: int | None
    active_inference: bool
    tool_history: Annotated[list[dict[str, Any]], add]
    tool_iteration: int
    max_tool_iterations: int
    tools_enabled: bool


# ── Writer + chunk helpers ───────────────────────────────────────────────


ChunkWriter = Callable[[GraphChunk], None]


def _emit(writer: ChunkWriter | None, chunk: GraphChunk) -> None:
    if writer is not None:
        try:
            writer(chunk)
        except Exception:
            # writer failure must not break the graph
            pass


def _get_writer_from_runnable_config(config: Any) -> ChunkWriter | None:
    """LangGraph passes `config` as the second arg to nodes. We follow the
    same `configurable.writer` convention the TS daemon uses so HTTP SSE
    can multiplex graph events without going through AsyncLocalStorage."""
    if isinstance(config, dict):
        configurable = config.get("configurable")
        if isinstance(configurable, dict):
            w = configurable.get("writer")
            if callable(w):
                return w  # type: ignore[no-any-return]
    return None


# ── Lexical surprise ─────────────────────────────────────────────────────


_WORD_RE = re.compile(r"[\w]+", re.UNICODE)


def _tokens(s: str) -> set[str]:
    return set(_WORD_RE.findall(s.lower()))


def lexical_surprise(predicted: str, actual: str) -> int:
    if not predicted or not actual:
        return 5
    a, b = _tokens(predicted), _tokens(actual)
    if not a and not b:
        return 5
    inter = len(a & b)
    union = len(a | b)
    j = (inter / union) if union > 0 else 1.0
    return round((1.0 - j) * 10.0)


def build_active_inference_context(state: AmenoState) -> str:
    if not state.get("active_inference"):
        return ""
    if state.get("surprise") is None or not state.get("prediction"):
        return ""
    last_user = next(
        (m for m in reversed(state.get("messages", [])) if m.get("role") == "user"),
        None,
    )
    actual = (last_user or {}).get("content", "")
    surprise = state["surprise"]
    lines = [
        f'Last turn you predicted the user would say: "{state["prediction"]}".',
        f'The user actually said: "{actual}".',
        f"Surprise score: {surprise}/10 (lexical Jaccard).",
    ]
    if surprise is not None and surprise >= 7:
        lines.append("Treat the user's intent as having shifted; ask a short clarifying question.")
    elif surprise is not None and surprise <= 2:
        lines.append("Your model of the user is on track; proceed confidently.")
    return "\n".join(lines)


def _parse_critique(raw: str) -> dict[str, Any]:
    m = re.search(r"\{[\s\S]*?\}", raw)
    if not m:
        return {"score": 7, "feedback": "(critic returned no JSON; accepting)"}
    try:
        obj = json.loads(m.group(0))
        if not isinstance(obj, dict):
            return {"score": 7, "feedback": "(critic JSON not an object; accepting)"}
        score_raw = obj.get("score")
        score = max(0, min(10, round(score_raw))) if isinstance(score_raw, (int, float)) else 7
        feedback_raw = obj.get("feedback")
        feedback = feedback_raw[:240] if isinstance(feedback_raw, str) else "(no feedback)"
        return {"score": score, "feedback": feedback}
    except json.JSONDecodeError:
        return {"score": 7, "feedback": "(critic JSON unparseable; accepting)"}


# ── Node functions ───────────────────────────────────────────────────────


async def surprise_eval_node(state: AmenoState, config: RunnableConfig) -> dict[str, Any]:
    writer = _get_writer_from_runnable_config(config)
    _emit(writer, {"type": "phase", "phase": "surprise_eval", "iteration": 0})
    last_user = next(
        (m for m in reversed(state.get("messages", [])) if m.get("role") == "user"),
        None,
    )
    actual = (last_user or {}).get("content", "")
    predicted = state.get("prediction", "")
    surprise = lexical_surprise(predicted, actual)
    _emit(
        writer,
        {
            "type": "surprise",
            "prediction": predicted,
            "actual": actual,
            "surprise": surprise,
            "mode": "lexical",
        },
    )
    return {"surprise": surprise}


async def generate_node(state: AmenoState, config: RunnableConfig) -> dict[str, Any]:
    writer = _get_writer_from_runnable_config(config)
    _emit(writer, {"type": "phase", "phase": "generate", "iteration": state.get("tool_iteration", 0)})

    preamble: list[ChatMessage] = []
    ai_ctx = build_active_inference_context(state)
    if ai_ctx:
        preamble.append({"role": "system", "content": ai_ctx})
    if state.get("tools_enabled"):
        preamble.append({"role": "system", "content": format_tools_for_prompt()})
        hist = format_tool_history(state.get("tool_history", []))
        if hist:
            preamble.append({"role": "system", "content": hist})

    prompt: list[ChatMessage] = preamble + state.get("messages", []) if preamble else state.get("messages", [])

    draft_parts: list[str] = []

    def on_token(tok: str) -> None:
        draft_parts.append(tok)
        _emit(writer, {"type": "token", "phase": "generate", "token": tok})

    stats = await runtime_generate(prompt, on_token)
    draft = "".join(draft_parts)
    _emit(writer, {"type": "stats", "phase": "generate", "stats": _stats_as_dict(stats)})
    return {"draft": draft}


async def execute_tool_node(state: AmenoState, config: RunnableConfig) -> dict[str, Any]:
    writer = _get_writer_from_runnable_config(config)
    next_iter = state.get("tool_iteration", 0) + 1
    _emit(writer, {"type": "phase", "phase": "execute_tool", "iteration": next_iter})

    calls = parse_tool_calls(state.get("draft", ""))
    appended: list[dict[str, Any]] = []
    for call in calls:
        _emit(
            writer,
            {
                "type": "tool_call",
                "name": call.name or "(unnamed)",
                "args": call.args,
                "iteration": next_iter,
            },
        )
        result = await execute_tool_call(call, {"messages": state.get("messages", [])})
        is_error = result.startswith("error:")
        _emit(
            writer,
            {
                "type": "tool_result",
                "name": call.name or "(unnamed)",
                "result": result,
                "error": is_error,
                "iteration": next_iter,
            },
        )
        appended.append(
            {"name": call.name or "(unnamed)", "args": call.args, "result": result}
        )
    return {"tool_history": appended, "tool_iteration": next_iter}


def decide_after_generate(state: AmenoState) -> Literal["execute_tool", "critic", "finalize"]:
    tool_iter = state.get("tool_iteration", 0)
    max_tool = state.get("max_tool_iterations", 3)
    if state.get("tools_enabled") and tool_iter < max_tool:
        calls = parse_tool_calls(state.get("draft", ""))
        if any(c.name and not c.parse_error for c in calls):
            return "execute_tool"
    if state.get("max_iterations", 0) > 0:
        return "critic"
    return "finalize"


async def critic_node(state: AmenoState, config: RunnableConfig) -> dict[str, Any]:
    writer = _get_writer_from_runnable_config(config)
    _emit(writer, {"type": "phase", "phase": "critique", "iteration": state.get("iteration", 0)})

    last_user = next(
        (m for m in reversed(state.get("messages", [])) if m.get("role") == "user"),
        None,
    )
    critique_prompt: list[ChatMessage] = [
        {
            "role": "system",
            "content": (
                "You are a strict reviewer. Read the user request and the assistant draft. "
                "Score the draft from 0 (terrible) to 10 (excellent) and give ONE specific "
                "actionable improvement. Reply with ONLY this JSON object on a single line, "
                'no prose: {"score": <int 0-10>, "feedback": "<one sentence>"}'
            ),
        },
        {
            "role": "user",
            "content": (
                f"# User request\n{(last_user or {}).get('content', '')}\n\n"
                f"# Assistant draft\n{state.get('draft','')}\n\n"
                f"Reply with the JSON object now."
            ),
        },
    ]

    raw_parts: list[str] = []

    def on_token(tok: str) -> None:
        raw_parts.append(tok)
        _emit(writer, {"type": "token", "phase": "critique", "token": tok})

    stats = await runtime_generate(critique_prompt, on_token)
    raw = "".join(raw_parts)
    _emit(writer, {"type": "stats", "phase": "critique", "stats": _stats_as_dict(stats)})

    parsed = _parse_critique(raw)
    _emit(
        writer,
        {
            "type": "critique",
            "score": parsed["score"],
            "feedback": parsed["feedback"],
            "iteration": state.get("iteration", 0),
        },
    )
    return {"critique": parsed}


async def revise_node(state: AmenoState, config: RunnableConfig) -> dict[str, Any]:
    writer = _get_writer_from_runnable_config(config)
    next_iter = state.get("iteration", 0) + 1
    _emit(writer, {"type": "phase", "phase": "revise", "iteration": next_iter})

    critique = state.get("critique") or {}
    revise_messages: list[ChatMessage] = list(state.get("messages", [])) + [
        {
            "role": "system",
            "content": (
                f"Your previous draft was:\n---\n{state.get('draft','')}\n---\n\n"
                f"A reviewer scored it {critique.get('score','?')}/10 and suggested: "
                f"{critique.get('feedback','(no feedback)')}\n\n"
                f"Rewrite the response addressing the suggestion. Output only the improved reply."
            ),
        }
    ]

    draft_parts: list[str] = []

    def on_token(tok: str) -> None:
        draft_parts.append(tok)
        _emit(writer, {"type": "token", "phase": "revise", "token": tok})

    stats = await runtime_generate(revise_messages, on_token)
    _emit(writer, {"type": "stats", "phase": "revise", "stats": _stats_as_dict(stats)})

    return {"draft": "".join(draft_parts), "iteration": next_iter}


def decide_continue(state: AmenoState) -> Literal["revise", "finalize"]:
    critique = state.get("critique") or {}
    score = critique.get("score", 10)
    if isinstance(score, (int, float)) and score >= 7:
        return "finalize"
    if state.get("iteration", 0) >= state.get("max_iterations", 1):
        return "finalize"
    return "revise"


def finalize_node(state: AmenoState, config: RunnableConfig) -> dict[str, Any]:
    writer = _get_writer_from_runnable_config(config)
    _emit(writer, {"type": "phase", "phase": "finalize", "iteration": state.get("iteration", 0)})
    draft = state.get("draft", "")
    visible = strip_tool_markup(draft) if state.get("tools_enabled") else draft
    if not visible:
        visible = draft
    return {"messages": [{"role": "assistant", "content": visible}]}


async def predict_next_node(state: AmenoState, config: RunnableConfig) -> dict[str, Any]:
    writer = _get_writer_from_runnable_config(config)
    _emit(writer, {"type": "phase", "phase": "predict_next", "iteration": 0})

    predict_prompt: list[ChatMessage] = [
        {
            "role": "system",
            "content": (
                "Based on the conversation so far, predict in ONE short sentence "
                "(<= 20 words) the user's most likely next message. Output ONLY the "
                "predicted sentence, no quotes, no preamble, no explanation."
            ),
        },
        *state.get("messages", []),
    ]

    raw_parts: list[str] = []

    def on_token(tok: str) -> None:
        raw_parts.append(tok)
        _emit(writer, {"type": "token", "phase": "predict_next", "token": tok})

    stats = await runtime_generate(predict_prompt, on_token)
    _emit(writer, {"type": "stats", "phase": "predict_next", "stats": _stats_as_dict(stats)})
    prediction = "".join(raw_parts).strip().strip("\"'")[:240]
    _emit(writer, {"type": "prediction", "prediction": prediction})
    return {"prediction": prediction}


def _stats_as_dict(stats: GenerationStats) -> dict[str, Any]:
    return {
        "durationMs": stats.duration_ms,
        "totalTokens": stats.total_tokens,
        "tokensPerSecond": stats.tokens_per_second,
        "ragActive": stats.rag_active,
    }


# ── Build & invoke ───────────────────────────────────────────────────────


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """Compile the ameno StateGraph. Default checkpointer is an in-memory
    MemorySaver; pass a FileCheckpointer for daemon persistence."""
    g = StateGraph(AmenoState)
    g.add_node("surprise_eval", surprise_eval_node)
    g.add_node("generate", generate_node)
    g.add_node("execute_tool", execute_tool_node)
    g.add_node("critic", critic_node)
    g.add_node("revise", revise_node)
    g.add_node("finalize", finalize_node)
    g.add_node("predict_next", predict_next_node)

    def _start_router(state: AmenoState) -> Literal["surprise_eval", "generate"]:
        return "surprise_eval" if state.get("active_inference") else "generate"

    def _finalize_router(state: AmenoState) -> Literal["predict_next", "__end__"]:
        return "predict_next" if state.get("active_inference") else END  # type: ignore[return-value]

    g.add_conditional_edges(START, _start_router)
    g.add_edge("surprise_eval", "generate")
    g.add_conditional_edges("generate", decide_after_generate)
    g.add_edge("execute_tool", "generate")
    g.add_conditional_edges("critic", decide_continue)
    g.add_edge("revise", "critic")
    g.add_conditional_edges("finalize", _finalize_router)
    g.add_edge("predict_next", END)

    return g.compile(checkpointer=checkpointer)


def _maybe_mst_checkpointer() -> BaseCheckpointSaver | None:
    """Auto-attach MstCheckpointSaver when MST_CHECKPOINT_SOCKET is set.

    Per ADR-2605171800 + ADR-2605172000 (RW-free substrate). The saver
    proxies every put / putWrites / getTuple / list call to the
    `@etzhayyim/sdk` TS sidecar over a Unix-domain socket (or
    `tcp://host:port` for out-of-host integration tests). Substrate
    pipeline ownership therefore lives *in the sidecar* — this Python
    process stays free of MST / IPFS / viem imports per ADR-2605172100.

    Returns None when the env var is unset so the caller can fall back
    to FileCheckpointer (the Path A / Path B local persistence). This
    keeps `kotodama.projects.ameno` runnable both on a developer
    laptop (no sidecar) and inside the lg-ameno K8s pod (sidecar
    container present, ADR-2605191257 §Stage 2).
    """
    socket_path = os.environ.get("MST_CHECKPOINT_SOCKET")
    if not socket_path:
        return None
    cell_did = os.environ.get(
        "MST_CHECKPOINT_CELL_DID", "did:web:ameno.etzhayyim.com"
    )
    # Lazy import — kotodama.checkpointer pulls msgpack, an optional
    # dependency for hosts that don't enable the substrate pipeline.
    from kotodama.checkpointer import MstCheckpointSaver

    return MstCheckpointSaver(cell_did=cell_did, socket_path=socket_path)


def _compile_default() -> Any:
    """Compile a default graph: MstCheckpointSaver when env says so,
    otherwise no checkpointer (callers can attach FileCheckpointer
    explicitly via `build_graph(saver)`)."""
    saver = _maybe_mst_checkpointer()
    return build_graph(saver)


# Module-level `app` export, mirroring the uhl_right_neural shape.
# langgraph CLI and kotodama.projects.ameno.server both pick this up
# when MST_CHECKPOINT_SOCKET is set in the deployment env.
app = _compile_default()


async def invoke_ameno(
    *,
    messages: list[ChatMessage],
    max_iterations: int = 0,
    active_inference: bool = False,
    tools_enabled: bool = True,
    thread_id: str = "default",
    on_chunk: ChunkWriter | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    graph: Any | None = None,
) -> str:
    """Drive one user turn through the graph, optionally streaming chunks.

    Mirrors the TS daemon's invokeDaemon. The compiled graph is reused
    across calls when passed in; otherwise we build a one-shot graph.
    """
    g = graph or build_graph(checkpointer)
    initial: AmenoState = {
        "messages": messages,
        "draft": "",
        "critique": None,
        "iteration": 0,
        "max_iterations": max_iterations,
        "prediction": "",
        "surprise": None,
        "active_inference": active_inference,
        "tool_history": [],
        "tool_iteration": 0,
        "max_tool_iterations": 3,
        "tools_enabled": tools_enabled,
    }
    config = {"configurable": {"thread_id": thread_id, "writer": on_chunk}}
    final_state = await g.ainvoke(initial, config=config)
    return (final_state or {}).get("draft", "") if isinstance(final_state, dict) else ""
