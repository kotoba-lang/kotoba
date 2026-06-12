"""MotoBodyPaintCell — futawa R0 Pregel cell (L4)."""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    BodyPaintPhase,
    transition_to_panel_verified,
    transition_to_artwork_charter_scanned,
    transition_to_painted,
    transition_to_cure_qa,
    transition_to_attestation_emitted,
)


class MotoBodyPaintCell:
    """L4 body panel + paint + G5 Charter artwork scan (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("panel", self._panel)
        graph.add_node("charter", self._charter)
        graph.add_node("paint", self._paint)
        graph.add_node("cure", self._cure)
        graph.add_node("attestation", self._attestation)
        graph.add_edge(START, "init")
        graph.add_edge("init", "panel")
        graph.add_edge("panel", "charter")
        graph.add_edge("charter", "paint")
        graph.add_edge("paint", "cure")
        graph.add_edge("cure", "attestation")
        graph.add_edge("attestation", END)
        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"body_paint_state": {"phase": BodyPaintPhase.INIT.value, "vehicleId": state.get("vehicleId", "FUTAWA-V-0001"), "completionPct": 0}}

    def _panel(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_panel_verified(state)

    def _charter(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_artwork_charter_scanned(state)

    def _paint(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_painted(state)

    def _cure(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_cure_qa(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("futawa R0 scaffold: activate via Council ADR-2605261345 post-ratification")


__all__ = ["MotoBodyPaintCell"]
