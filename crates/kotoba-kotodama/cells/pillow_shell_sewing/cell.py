"""PillowShellSewingCell — makura R0 Pregel cell (L4b)."""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    ShellSewingPhase,
    transition_to_pattern_loaded,
    transition_to_fabric_cut,
    transition_to_serge_stitched,
    transition_to_inspection,
    transition_to_shell_ready,
)


class PillowShellSewingCell:
    """L4b three-side serge stitch shell assembly (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("pattern", self._pattern)
        graph.add_node("cut", self._cut)
        graph.add_node("stitch", self._stitch)
        graph.add_node("inspection", self._inspection)
        graph.add_node("ready", self._ready)

        graph.add_edge(START, "init")
        graph.add_edge("init", "pattern")
        graph.add_edge("pattern", "cut")
        graph.add_edge("cut", "stitch")
        graph.add_edge("stitch", "inspection")
        graph.add_edge("inspection", "ready")
        graph.add_edge("ready", END)

        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "shell_sewing_state": {
                "phase": ShellSewingPhase.INIT.value,
                "lotId": state.get("lotId", "MAKURA-PILLOW-LOT-0001"),
                "completionPct": 0,
            }
        }

    def _pattern(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_pattern_loaded(state)

    def _cut(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_fabric_cut(state)

    def _stitch(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_serge_stitched(state)

    def _inspection(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_inspection(state)

    def _ready(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_shell_ready(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(
            "makura R0 scaffold: activate via Council ADR-2605261130 post-ratification"
        )


__all__ = ["PillowShellSewingCell"]
