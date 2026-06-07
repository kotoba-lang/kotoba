"""ElvEmissionsAuditCell — hodoki R0 Pregel cell (cross-cutting)."""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    EmissionsAuditPhase,
    transition_to_fgas_aggregated,
    transition_to_asr_aggregated,
    transition_to_pgm_yield_verified,
    transition_to_compliance_finalized,
)


class ElvEmissionsAuditCell:
    """Cross-cutting F-gas + ASR + PGM compliance audit (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("fgas", self._fgas)
        graph.add_node("asr", self._asr)
        graph.add_node("pgm", self._pgm)
        graph.add_node("compliance", self._compliance)

        graph.add_edge(START, "init")
        graph.add_edge("init", "fgas")
        graph.add_edge("fgas", "asr")
        graph.add_edge("asr", "pgm")
        graph.add_edge("pgm", "compliance")
        graph.add_edge("compliance", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "emissions_audit_state": {
                "phase": EmissionsAuditPhase.INIT.value,
                "vehicleId": state.get("vehicleId", "HODOKI-VEHICLE-0001"),
                "completionPct": 0,
            }
        }

    def _fgas(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_fgas_aggregated(state)

    def _asr(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_asr_aggregated(state)

    def _pgm(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_pgm_yield_verified(state)

    def _compliance(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_compliance_finalized(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(
            "hodoki R0 scaffold: activate via Council ADR-2605261230 post-ratification"
        )


__all__ = ["ElvEmissionsAuditCell"]
