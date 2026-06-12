"""ElvDepollutionCell — hodoki R0 Pregel cell (L1b).

Per ADR-2605261215 §6 L1b: fluid drain + MAC F-gas capture ≥95% (G6) + airbag
pyrotechnic neutralization + battery disconnect + G8 cryptographic data wipe
(MANDATORY before any disassembly). R0 scaffold — .solve() raises.
"""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    DepollutionPhase,
    transition_to_data_wipe_completed,
    transition_to_fluids_drained,
    transition_to_fgas_captured,
    transition_to_airbags_neutralized,
    transition_to_battery_disconnected,
    transition_to_attestation_emitted,
)


class ElvDepollutionCell:
    """L1b ELV depollution + G6 F-gas + G7 airbag + G8 data wipe (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("data_wipe", self._data_wipe)
        graph.add_node("fluids", self._fluids)
        graph.add_node("fgas", self._fgas)
        graph.add_node("airbags", self._airbags)
        graph.add_node("battery", self._battery)
        graph.add_node("attestation", self._attestation)

        graph.add_edge(START, "init")
        graph.add_edge("init", "data_wipe")
        graph.add_edge("data_wipe", "fluids")
        graph.add_edge("fluids", "fgas")
        graph.add_edge("fgas", "airbags")
        graph.add_edge("airbags", "battery")
        graph.add_edge("battery", "attestation")
        graph.add_edge("attestation", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "depollution_state": {
                "phase": DepollutionPhase.INIT.value,
                "vehicleId": state.get("vehicleId", "HODOKI-VEHICLE-0001"),
                "completionPct": 0,
            }
        }

    def _data_wipe(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_data_wipe_completed(state)

    def _fluids(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_fluids_drained(state)

    def _fgas(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_fgas_captured(state)

    def _airbags(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_airbags_neutralized(state)

    def _battery(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_battery_disconnected(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(
            "hodoki R0 scaffold: activate via Council ADR-2605261230 post-ratification"
        )


__all__ = ["ElvDepollutionCell"]
