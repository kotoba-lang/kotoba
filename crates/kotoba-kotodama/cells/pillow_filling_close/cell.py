"""PillowFillingCloseCell — makura R0 Pregel cell (L5a)."""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    FillClosePhase,
    transition_to_shell_received,
    transition_to_crumb_dispensed,
    transition_to_close_stitched,
    transition_to_label_attached,
    transition_to_attestation_emitted,
)


class PillowFillingCloseCell:
    """L5a crumb fill + close stitch + bilingual label + take-back QR (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("shell_received", self._shell_received)
        graph.add_node("fill", self._fill)
        graph.add_node("close", self._close)
        graph.add_node("label", self._label)
        graph.add_node("attestation", self._attestation)

        graph.add_edge(START, "init")
        graph.add_edge("init", "shell_received")
        graph.add_edge("shell_received", "fill")
        graph.add_edge("fill", "close")
        graph.add_edge("close", "label")
        graph.add_edge("label", "attestation")
        graph.add_edge("attestation", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "fill_close_state": {
                "phase": FillClosePhase.INIT.value,
                "lotId": state.get("lotId", "MAKURA-PILLOW-LOT-0001"),
                "pillowSerial": state.get("pillowSerial", "MK-2026-0000001"),
                "completionPct": 0,
            }
        }

    def _shell_received(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_shell_received(state)

    def _fill(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_crumb_dispensed(state)

    def _close(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_close_stitched(state)

    def _label(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_label_attached(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(
            "makura R0 scaffold: activate via Council ADR-2605261130 post-ratification"
        )


__all__ = ["PillowFillingCloseCell"]
