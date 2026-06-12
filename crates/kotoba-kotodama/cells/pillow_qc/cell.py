"""PillowQcCell — makura R0 Pregel cell (L5b)."""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    QcPhase,
    transition_to_dimensional,
    transition_to_weight,
    transition_to_ild,
    transition_to_visual,
    transition_to_attestation_emitted,
)


class PillowQcCell:
    """L5b dimensional + weight + ILD + visual defect QC (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("dimensional", self._dimensional)
        graph.add_node("weight", self._weight)
        graph.add_node("ild", self._ild)
        graph.add_node("visual", self._visual)
        graph.add_node("attestation", self._attestation)

        graph.add_edge(START, "init")
        graph.add_edge("init", "dimensional")
        graph.add_edge("dimensional", "weight")
        graph.add_edge("weight", "ild")
        graph.add_edge("ild", "visual")
        graph.add_edge("visual", "attestation")
        graph.add_edge("attestation", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "qc_state": {
                "phase": QcPhase.INIT.value,
                "lotId": state.get("lotId", "MAKURA-PILLOW-LOT-0001"),
                "pillowSerial": state.get("pillowSerial", "MK-2026-0000001"),
                "completionPct": 0,
            }
        }

    def _dimensional(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_dimensional(state)

    def _weight(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_weight(state)

    def _ild(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_ild(state)

    def _visual(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_visual(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(
            "makura R0 scaffold: activate via Council ADR-2605261130 post-ratification"
        )


__all__ = ["PillowQcCell"]
