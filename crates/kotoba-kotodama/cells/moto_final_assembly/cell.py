"""MotoFinalAssemblyCell — futawa R0 Pregel cell (L5a).

CONSTITUTIONAL FIRSTS: G12 right-to-repair forward-publishing + G13 hodoki
pre-registration. R0 scaffold.
"""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    FinalAssemblyPhase,
    transition_to_subassemblies_mated,
    transition_to_fluids_filled,
    transition_to_vin_tagged,
    transition_to_parts_catalog_published,
    transition_to_hodoki_pre_registered,
    transition_to_attestation_emitted,
)


class MotoFinalAssemblyCell:
    """L5a final assembly + G12 parts catalog publication + G13 hodoki pre-reg (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("mate", self._mate)
        graph.add_node("fluids", self._fluids)
        graph.add_node("vin", self._vin)
        graph.add_node("catalog", self._catalog)
        graph.add_node("hodoki", self._hodoki)
        graph.add_node("attestation", self._attestation)
        graph.add_edge(START, "init")
        graph.add_edge("init", "mate")
        graph.add_edge("mate", "fluids")
        graph.add_edge("fluids", "vin")
        graph.add_edge("vin", "catalog")
        graph.add_edge("catalog", "hodoki")
        graph.add_edge("hodoki", "attestation")
        graph.add_edge("attestation", END)
        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "final_assembly_state": {
                "phase": FinalAssemblyPhase.INIT.value,
                "vehicleId": state.get("vehicleId", "FUTAWA-V-0001"),
                "vin": state.get("vin", "ETZFUTAWA250R0A0000001"),
                "completionPct": 0,
            }
        }

    def _mate(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_subassemblies_mated(state)

    def _fluids(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_fluids_filled(state)

    def _vin(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_vin_tagged(state)

    def _catalog(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_parts_catalog_published(state)

    def _hodoki(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_hodoki_pre_registered(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("futawa R0 scaffold: activate via Council ADR-2605261345 post-ratification")


__all__ = ["MotoFinalAssemblyCell"]
