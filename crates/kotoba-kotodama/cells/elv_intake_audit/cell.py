"""ElvIntakeAuditCell — hodoki R0 Pregel cell (L1a).

Per ADR-2605261215 §6 L1a: VIN title verification + prior-owner consent +
Charter §2(a-h) scan + initial data-wipe attestation request.
R0 scaffold — .solve() raises until Council Lv6+ ratifies ADR-2605261230.
"""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    IntakePhase,
    transition_to_vin_verified,
    transition_to_consent_received,
    transition_to_charter_scanned,
    transition_to_data_wipe_requested,
    transition_to_attestation_emitted,
)


class ElvIntakeAuditCell:
    """L1a ELV intake audit + Charter scan + data-wipe request (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("vin", self._vin)
        graph.add_node("consent", self._consent)
        graph.add_node("charter", self._charter)
        graph.add_node("data_wipe_request", self._data_wipe_request)
        graph.add_node("attestation", self._attestation)

        graph.add_edge(START, "init")
        graph.add_edge("init", "vin")
        graph.add_edge("vin", "consent")
        graph.add_edge("consent", "charter")
        graph.add_edge("charter", "data_wipe_request")
        graph.add_edge("data_wipe_request", "attestation")
        graph.add_edge("attestation", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "intake_state": {
                "phase": IntakePhase.INIT.value,
                "vehicleId": state.get("vehicleId", "HODOKI-VEHICLE-0001"),
                "completionPct": 0,
            }
        }

    def _vin(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_vin_verified(state)

    def _consent(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_consent_received(state)

    def _charter(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_charter_scanned(state)

    def _data_wipe_request(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_data_wipe_requested(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        """Execute the cell — R0 scaffold raises until R1 activation."""
        raise RuntimeError(
            "hodoki R0 scaffold: activate via Council ADR-2605261230 post-ratification"
        )


__all__ = ["ElvIntakeAuditCell"]
