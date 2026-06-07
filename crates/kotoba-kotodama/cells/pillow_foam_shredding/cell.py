"""PillowFoamShreddingCell — makura R0 Pregel cell (L3)."""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    FoamShreddingPhase,
    transition_to_slab_loaded,
    transition_to_shredded,
    transition_to_particle_qc,
    transition_to_recycled_blend_mixed,
    transition_to_crumb_ready,
)


class PillowFoamShreddingCell:
    """L3 foam shredding to crumb + recycled blend (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("load_slab", self._load_slab)
        graph.add_node("shred", self._shred)
        graph.add_node("particle_qc", self._particle_qc)
        graph.add_node("recycled_blend", self._recycled_blend)
        graph.add_node("ready", self._ready)

        graph.add_edge(START, "init")
        graph.add_edge("init", "load_slab")
        graph.add_edge("load_slab", "shred")
        graph.add_edge("shred", "particle_qc")
        graph.add_edge("particle_qc", "recycled_blend")
        graph.add_edge("recycled_blend", "ready")
        graph.add_edge("ready", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "foam_shredding_state": {
                "phase": FoamShreddingPhase.INIT.value,
                "batchId": state.get("batchId", "MAKURA-BATCH-0001"),
                "completionPct": 0,
            }
        }

    def _load_slab(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_slab_loaded(state)

    def _shred(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_shredded(state)

    def _particle_qc(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_particle_qc(state)

    def _recycled_blend(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_recycled_blend_mixed(state)

    def _ready(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_crumb_ready(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(
            "makura R0 scaffold: activate via Council ADR-2605261130 post-ratification"
        )


__all__ = ["PillowFoamShreddingCell"]
