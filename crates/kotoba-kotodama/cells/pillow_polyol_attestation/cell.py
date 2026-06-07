"""PillowPolyolAttestationCell — makura R0 Pregel cell (L1a).

Per ADR-2605261115 §6 L1a: polyol + catalyst + surfactant + blowing-agent
raw-material attestation, bio-content disclosed, no Hg/Sn catalysts.
R0 scaffold — .solve() raises RuntimeError until Council Lv6+ ratifies
ADR-2605261130 (R1 activation).
"""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    PolyolPhase,
    PolyolState,
    transition_to_polyol_verified,
    transition_to_catalyst_verified,
    transition_to_surfactant_verified,
    transition_to_attestation_emitted,
)


class PillowPolyolAttestationCell:
    """L1a polyol + catalyst + surfactant raw-material attestation (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("polyol", self._polyol)
        graph.add_node("catalyst", self._catalyst)
        graph.add_node("surfactant", self._surfactant)
        graph.add_node("attestation", self._attestation)

        graph.add_edge(START, "init")
        graph.add_edge("init", "polyol")
        graph.add_edge("polyol", "catalyst")
        graph.add_edge("catalyst", "surfactant")
        graph.add_edge("surfactant", "attestation")
        graph.add_edge("attestation", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "polyol_state": {
                "phase": PolyolPhase.INIT.value,
                "batchId": state.get("batchId", "MAKURA-BATCH-0001"),
                "completionPct": 0,
            }
        }

    def _polyol(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_polyol_verified(state)

    def _catalyst(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_catalyst_verified(state)

    def _surfactant(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_surfactant_verified(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        """Execute the cell — R0 scaffold raises until R1 activation."""
        raise RuntimeError(
            "makura R0 scaffold: activate via Council ADR-2605261130 post-ratification"
        )


__all__ = ["PillowPolyolAttestationCell"]
