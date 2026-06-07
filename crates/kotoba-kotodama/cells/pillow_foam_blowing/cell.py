"""PillowFoamBlowingCell — makura R0 Pregel cell (L2).

Per ADR-2605261115 §6 L2: slabstock one-shot foam blowing; density + cell-
structure + VOC QA. R0 scaffold — .solve() raises.
"""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    FoamBlowingPhase,
    transition_to_streams_verified,
    transition_to_blown,
    transition_to_cured,
    transition_to_qc_passed,
    transition_to_attestation_emitted,
)


class PillowFoamBlowingCell:
    """L2 slabstock foam blowing + QA (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("streams", self._streams)
        graph.add_node("blown", self._blown)
        graph.add_node("cured", self._cured)
        graph.add_node("qc", self._qc)
        graph.add_node("attestation", self._attestation)

        graph.add_edge(START, "init")
        graph.add_edge("init", "streams")
        graph.add_edge("streams", "blown")
        graph.add_edge("blown", "cured")
        graph.add_edge("cured", "qc")
        graph.add_edge("qc", "attestation")
        graph.add_edge("attestation", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "foam_blowing_state": {
                "phase": FoamBlowingPhase.INIT.value,
                "batchId": state.get("batchId", "MAKURA-BATCH-0001"),
                "completionPct": 0,
            }
        }

    def _streams(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_streams_verified(state)

    def _blown(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_blown(state)

    def _cured(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_cured(state)

    def _qc(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_qc_passed(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        """Execute the cell — R0 scaffold raises until R1 activation."""
        raise RuntimeError(
            "makura R0 scaffold: activate via Council ADR-2605261130 post-ratification"
        )


__all__ = ["PillowFoamBlowingCell"]
