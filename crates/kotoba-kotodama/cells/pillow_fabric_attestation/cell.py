"""PillowFabricAttestationCell — makura R0 Pregel cell (L4a)."""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    FabricPhase,
    transition_to_source_verified,
    transition_to_dye_verified,
    transition_to_charter_scanned,
    transition_to_attestation_emitted,
)


class PillowFabricAttestationCell:
    """L4a fabric source + dye safety + Charter scan attestation (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("source", self._source)
        graph.add_node("dye", self._dye)
        graph.add_node("charter", self._charter)
        graph.add_node("attestation", self._attestation)

        graph.add_edge(START, "init")
        graph.add_edge("init", "source")
        graph.add_edge("source", "dye")
        graph.add_edge("dye", "charter")
        graph.add_edge("charter", "attestation")
        graph.add_edge("attestation", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "fabric_state": {
                "phase": FabricPhase.INIT.value,
                "lotId": state.get("lotId", "MAKURA-FABRIC-LOT-0237"),
                "completionPct": 0,
            }
        }

    def _source(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_source_verified(state)

    def _dye(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_dye_verified(state)

    def _charter(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_charter_scanned(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(
            "makura R0 scaffold: activate via Council ADR-2605261130 post-ratification"
        )


__all__ = ["PillowFabricAttestationCell"]
