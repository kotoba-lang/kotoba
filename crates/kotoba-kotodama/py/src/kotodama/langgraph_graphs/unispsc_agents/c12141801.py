# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141801"
UNISPSC_TITLE = "Graph"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Segment 12 "Graph" (biological data recording and analysis)
    subject_id: str
    data_series: list[float]
    recording_interval_sec: int
    is_anomaly_detected: bool
    quality_score: float


def capture_data(state: State) -> dict[str, Any]:
    """Captures and validates graph data points for the biological subject."""
    inp = state.get("input") or {}
    series = inp.get("data", [])
    sid = inp.get("subject_id", "CAPT-12141801")
    interval = inp.get("interval_seconds", 3600)

    return {
        "log": [f"{UNISPSC_CODE}:capture_data"],
        "subject_id": sid,
        "data_series": series,
        "recording_interval_sec": interval,
    }


def evaluate_series(state: State) -> dict[str, Any]:
    """Evaluates the data series for biological anomalies and calculates quality score."""
    series = state.get("data_series", [])
    # Simple anomaly check: any value outside a reasonable biological range
    anomaly = any(v < 0 or v > 5000 for v in series) if series else False

    # Calculate a mock quality score based on data density
    score = min(1.0, len(series) / 10.0) if series else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_series"],
        "is_anomaly_detected": anomaly,
        "quality_score": score,
    }


def compile_result(state: State) -> dict[str, Any]:
    """Compiles the final result for the Graph actor based on analyzed state."""
    return {
        "log": [f"{UNISPSC_CODE}:compile_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "subject": state.get("subject_id"),
            "anomaly_detected": state.get("is_anomaly_detected"),
            "quality_score": state.get("quality_score"),
            "points_analyzed": len(state.get("data_series", [])),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("capture", capture_data)
_g.add_node("evaluate", evaluate_series)
_g.add_node("compile", compile_result)

_g.add_edge(START, "capture")
_g.add_edge("capture", "evaluate")
_g.add_edge("evaluate", "compile")
_g.add_edge("compile", END)

graph = _g.compile()
