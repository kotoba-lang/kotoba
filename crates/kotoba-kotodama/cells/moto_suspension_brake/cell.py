"""MotoSuspensionBrakeCell — futawa R0 Pregel cell (L3b).

CONSTITUTIONAL FIRST G7: ABS-mandatory ≥125cc / electric ≥6kW.
"""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    SuspensionBrakePhase,
    transition_to_fork_installed,
    transition_to_shock_installed,
    transition_to_brake_installed,
    transition_to_abs_verified,
    transition_to_attestation_emitted,
)


class MotoSuspensionBrakeCell:
    """L3b suspension + brake + G7 ABS-mandatory (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("fork", self._fork)
        graph.add_node("shock", self._shock)
        graph.add_node("brake", self._brake)
        graph.add_node("abs", self._abs)
        graph.add_node("attestation", self._attestation)
        graph.add_edge(START, "init")
        graph.add_edge("init", "fork")
        graph.add_edge("fork", "shock")
        graph.add_edge("shock", "brake")
        graph.add_edge("brake", "abs")
        graph.add_edge("abs", "attestation")
        graph.add_edge("attestation", END)
        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "suspension_brake_state": {
                "phase": SuspensionBrakePhase.INIT.value,
                "vehicleId": state.get("vehicleId", "FUTAWA-V-0001"),
                "displacementCc": state.get("displacementCc", 248),
                "completionPct": 0,
            }
        }

    def _fork(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_fork_installed(state)

    def _shock(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_shock_installed(state)

    def _brake(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_brake_installed(state)

    def _abs(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_abs_verified(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("futawa R0 scaffold: activate via Council ADR-2605261345 post-ratification")


__all__ = ["MotoSuspensionBrakeCell"]
