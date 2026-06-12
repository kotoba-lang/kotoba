"""ElvPartsHarvestCell — hodoki R0 Pregel cell (L3a).

CONSTITUTIONAL FIRST: G12 right-to-repair invariant — every harvested part
gets IPFS-pinned catalog entry with VIN provenance + part DID + condition
grade + bilingual description. §2(e) anti-gatekeeping operationalized.
"""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    PartsHarvestPhase,
    transition_to_parts_identified,
    transition_to_condition_graded,
    transition_to_part_dids_issued,
    transition_to_catalog_published,
    transition_to_attestation_emitted,
)


class ElvPartsHarvestCell:
    """L3a parts harvest + right-to-repair catalog publication (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("identify", self._identify)
        graph.add_node("grade", self._grade)
        graph.add_node("issue_dids", self._issue_dids)
        graph.add_node("publish", self._publish)
        graph.add_node("attestation", self._attestation)

        graph.add_edge(START, "init")
        graph.add_edge("init", "identify")
        graph.add_edge("identify", "grade")
        graph.add_edge("grade", "issue_dids")
        graph.add_edge("issue_dids", "publish")
        graph.add_edge("publish", "attestation")
        graph.add_edge("attestation", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "parts_harvest_state": {
                "phase": PartsHarvestPhase.INIT.value,
                "vehicleId": state.get("vehicleId", "HODOKI-VEHICLE-0001"),
                "vin": state.get("vin", "WAUZZZ8V3MA000001"),
                "completionPct": 0,
            }
        }

    def _identify(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_parts_identified(state)

    def _grade(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_condition_graded(state)

    def _issue_dids(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_part_dids_issued(state)

    def _publish(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_catalog_published(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(
            "hodoki R0 scaffold: activate via Council ADR-2605261230 post-ratification"
        )


__all__ = ["ElvPartsHarvestCell"]
