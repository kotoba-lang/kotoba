"""ElvCatalystRecoveryCell — hodoki R0 Pregel cell (L3b)."""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    CatalystPhase,
    transition_to_brick_removed,
    transition_to_brick_weighed,
    transition_to_smelter_handoff,
    transition_to_yield_audited,
    transition_to_attestation_emitted,
)


class ElvCatalystRecoveryCell:
    """L3b PGM recovery from catalytic converter (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("remove", self._remove)
        graph.add_node("weigh", self._weigh)
        graph.add_node("smelter", self._smelter)
        graph.add_node("yield_audit", self._yield_audit)
        graph.add_node("attestation", self._attestation)

        graph.add_edge(START, "init")
        graph.add_edge("init", "remove")
        graph.add_edge("remove", "weigh")
        graph.add_edge("weigh", "smelter")
        graph.add_edge("smelter", "yield_audit")
        graph.add_edge("yield_audit", "attestation")
        graph.add_edge("attestation", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "catalyst_state": {
                "phase": CatalystPhase.INIT.value,
                "vehicleId": state.get("vehicleId", "HODOKI-VEHICLE-0001"),
                "completionPct": 0,
            }
        }

    def _remove(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_brick_removed(state)

    def _weigh(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_brick_weighed(state)

    def _smelter(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_smelter_handoff(state)

    def _yield_audit(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_yield_audited(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(
            "hodoki R0 scaffold: activate via Council ADR-2605261230 post-ratification"
        )


__all__ = ["ElvCatalystRecoveryCell"]
