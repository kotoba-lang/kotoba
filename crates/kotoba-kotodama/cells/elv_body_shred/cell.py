"""ElvBodyShredCell — hodoki R0 Pregel cell (L4)."""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    BodyShredPhase,
    transition_to_hulk_loaded,
    transition_to_shredded,
    transition_to_sorted,
    transition_to_kanayama_handoff,
    transition_to_silicon_handoff,
    transition_to_attestation_emitted,
)


class ElvBodyShredCell:
    """L4 hulk shred + sort + cross-actor handoff to kanayama + silicon (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("load", self._load)
        graph.add_node("shred", self._shred)
        graph.add_node("sort", self._sort)
        graph.add_node("kanayama", self._kanayama)
        graph.add_node("silicon", self._silicon)
        graph.add_node("attestation", self._attestation)

        graph.add_edge(START, "init")
        graph.add_edge("init", "load")
        graph.add_edge("load", "shred")
        graph.add_edge("shred", "sort")
        graph.add_edge("sort", "kanayama")
        graph.add_edge("kanayama", "silicon")
        graph.add_edge("silicon", "attestation")
        graph.add_edge("attestation", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "body_shred_state": {
                "phase": BodyShredPhase.INIT.value,
                "vehicleId": state.get("vehicleId", "HODOKI-VEHICLE-0001"),
                "completionPct": 0,
            }
        }

    def _load(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_hulk_loaded(state)

    def _shred(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_shredded(state)

    def _sort(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_sorted(state)

    def _kanayama(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_kanayama_handoff(state)

    def _silicon(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_silicon_handoff(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(
            "hodoki R0 scaffold: activate via Council ADR-2605261230 post-ratification"
        )


__all__ = ["ElvBodyShredCell"]
