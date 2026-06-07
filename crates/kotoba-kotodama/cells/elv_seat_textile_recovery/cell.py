"""ElvSeatTextileRecoveryCell — hodoki R0 Pregel cell (L3c)."""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    SeatTextilePhase,
    transition_to_seats_removed,
    transition_to_foam_separated,
    transition_to_textile_sorted,
    transition_to_makura_handoff,
    transition_to_attestation_emitted,
)


class ElvSeatTextileRecoveryCell:
    """L3c seat foam + textile recovery + makura G13 cross-actor handoff (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("seats", self._seats)
        graph.add_node("foam", self._foam)
        graph.add_node("textile", self._textile)
        graph.add_node("makura_handoff", self._makura_handoff)
        graph.add_node("attestation", self._attestation)

        graph.add_edge(START, "init")
        graph.add_edge("init", "seats")
        graph.add_edge("seats", "foam")
        graph.add_edge("foam", "textile")
        graph.add_edge("textile", "makura_handoff")
        graph.add_edge("makura_handoff", "attestation")
        graph.add_edge("attestation", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "seat_textile_state": {
                "phase": SeatTextilePhase.INIT.value,
                "vehicleId": state.get("vehicleId", "HODOKI-VEHICLE-0001"),
                "completionPct": 0,
            }
        }

    def _seats(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_seats_removed(state)

    def _foam(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_foam_separated(state)

    def _textile(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_textile_sorted(state)

    def _makura_handoff(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_makura_handoff(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(
            "hodoki R0 scaffold: activate via Council ADR-2605261230 post-ratification"
        )


__all__ = ["ElvSeatTextileRecoveryCell"]
