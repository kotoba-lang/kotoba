"""LangGraph wrapper for Hume expression analysis.

Graph id: ``hume.emotion.analyze.v1``.
Task type: ``com.etzhayyim.agent.hume.emotion``.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from kotodama.primitives import hume_emotion
from kotodama.primitives import langgraph_registry


class HumeEmotionState(TypedDict, total=False):
    text: str
    urls: list[str]
    files: list[dict[str, Any]]
    fileBase64: str
    modality: str
    mode: str
    timeoutMs: int
    pollIntervalMs: int
    normalized: dict[str, Any]
    jobId: str
    selectedMode: str
    fallbackReason: str
    error: str
    model: dict[str, Any]


async def _analyze(state: HumeEmotionState) -> HumeEmotionState:
    text = state.get("text") or ""
    urls = state.get("urls") or []
    files = state.get("files") or []
    file_base64 = state.get("fileBase64") or ""
    if not text and not urls and not files and not file_base64:
        return {**state, "error": "text, urls, or files are required"}
    result = await hume_emotion.task_hume_expression_analyze(
        text=text,
        urls=urls,
        files=state.get("files") or [],
        fileBase64=state.get("fileBase64") or "",
        modality=state.get("modality") or "",
        mode=state.get("mode") or "auto",
        timeoutMs=int(state.get("timeoutMs") or 120_000),
        pollIntervalMs=int(state.get("pollIntervalMs") or 5_000),
    )
    return {
        **state,
        "normalized": result.get("normalized") or {},
        "jobId": result.get("jobId") or "",
        "selectedMode": result.get("mode") or "",
        "fallbackReason": result.get("fallbackReason") or "",
        "error": result.get("error") or "",
        "model": result.get("model") or {},
    }


def _build_graph() -> Any:
    graph = StateGraph(HumeEmotionState)
    graph.add_node("analyze", _analyze)
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", END)
    return graph.compile()


hume_emotion_graph = _build_graph()
langgraph_registry.register("hume.emotion.analyze.v1", hume_emotion_graph)


async def task_agent_hume_emotion(
    text: str = "",
    urls: list[str] | None = None,
    files: list[dict[str, Any]] | None = None,
    fileBase64: str = "",
    modality: str = "",
    mode: str = "auto",
    timeoutMs: int = 120_000,
    pollIntervalMs: int = 5_000,
) -> dict[str, Any]:
    final = await hume_emotion_graph.ainvoke(
        {
            "text": text,
            "urls": urls or [],
            "files": files or [],
            "fileBase64": fileBase64,
            "modality": modality,
            "mode": mode,
            "timeoutMs": timeoutMs,
            "pollIntervalMs": pollIntervalMs,
        }
    )
    return dict(final)
