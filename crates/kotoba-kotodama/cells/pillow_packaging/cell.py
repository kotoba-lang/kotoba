"""PillowPackagingCell — makura R0 Pregel cell (L5c)."""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    PackagingPhase,
    transition_to_vacuum_compressed,
    transition_to_cartoned,
    transition_to_palletized,
    transition_to_qr_pinned,
    transition_to_attestation_emitted,
)


class PillowPackagingCell:
    """L5c vacuum compression + carton + pallet + take-back QR (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("vacuum", self._vacuum)
        graph.add_node("carton", self._carton)
        graph.add_node("palletize", self._palletize)
        graph.add_node("qr_pin", self._qr_pin)
        graph.add_node("attestation", self._attestation)

        graph.add_edge(START, "init")
        graph.add_edge("init", "vacuum")
        graph.add_edge("vacuum", "carton")
        graph.add_edge("carton", "palletize")
        graph.add_edge("palletize", "qr_pin")
        graph.add_edge("qr_pin", "attestation")
        graph.add_edge("attestation", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "packaging_state": {
                "phase": PackagingPhase.INIT.value,
                "lotId": state.get("lotId", "MAKURA-PILLOW-LOT-0001"),
                "pillowSerial": state.get("pillowSerial", "MK-2026-0000001"),
                "completionPct": 0,
            }
        }

    def _vacuum(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_vacuum_compressed(state)

    def _carton(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_cartoned(state)

    def _palletize(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_palletized(state)

    def _qr_pin(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_qr_pinned(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(
            "makura R0 scaffold: activate via Council ADR-2605261130 post-ratification"
        )


__all__ = ["PillowPackagingCell"]
