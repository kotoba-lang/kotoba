"""PillowIsocyanateDispensingCell — makura R0 Pregel cell (L1b).

Per ADR-2605261115 §6 L1b: closed-loop MDI / TDI dispensing + worker exposure
log (G6: ≤ 5 ppb MDI / ≤ 2 ppb TDI 8h TWA). R0 scaffold — .solve() raises.
"""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    IsocyanatePhase,
    transition_to_lot_verified,
    transition_to_exposure_baseline,
    transition_to_dispensed,
    transition_to_exposure_final,
    transition_to_attestation_emitted,
)


class PillowIsocyanateDispensingCell:
    """L1b closed-loop isocyanate dispensing + worker exposure (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("verify_lot", self._verify_lot)
        graph.add_node("exposure_baseline", self._exposure_baseline)
        graph.add_node("dispense", self._dispense)
        graph.add_node("exposure_final", self._exposure_final)
        graph.add_node("attestation", self._attestation)

        graph.add_edge(START, "init")
        graph.add_edge("init", "verify_lot")
        graph.add_edge("verify_lot", "exposure_baseline")
        graph.add_edge("exposure_baseline", "dispense")
        graph.add_edge("dispense", "exposure_final")
        graph.add_edge("exposure_final", "attestation")
        graph.add_edge("attestation", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "isocyanate_state": {
                "phase": IsocyanatePhase.INIT.value,
                "batchId": state.get("batchId", "MAKURA-BATCH-0001"),
                "completionPct": 0,
            }
        }

    def _verify_lot(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_lot_verified(state)

    def _exposure_baseline(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_exposure_baseline(state)

    def _dispense(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_dispensed(state)

    def _exposure_final(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_exposure_final(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        """Execute the cell — R0 scaffold raises until R1 activation."""
        raise RuntimeError(
            "makura R0 scaffold: activate via Council ADR-2605261130 post-ratification"
        )


__all__ = ["PillowIsocyanateDispensingCell"]
