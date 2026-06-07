"""MotoTestDynoRoadCell — futawa R0 Pregel cell (L5b)."""

from typing import Any

from langgraph.graph import StateGraph, START, END

from .state_machine import (
    TestPhase,
    transition_to_dyno_run,
    transition_to_emissions_test,
    transition_to_sound_test,
    transition_to_abs_function_test,
    transition_to_road_test,
    transition_to_attestation_emitted,
)


class MotoTestDynoRoadCell:
    """L5b dyno + emissions + sound + ABS + road test (R0 scaffold)."""

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("init", self._initialize_state)
        graph.add_node("dyno", self._dyno)
        graph.add_node("emissions", self._emissions)
        graph.add_node("sound", self._sound)
        graph.add_node("abs", self._abs)
        graph.add_node("road", self._road)
        graph.add_node("attestation", self._attestation)
        graph.add_edge(START, "init")
        graph.add_edge("init", "dyno")
        graph.add_edge("dyno", "emissions")
        graph.add_edge("emissions", "sound")
        graph.add_edge("sound", "abs")
        graph.add_edge("abs", "road")
        graph.add_edge("road", "attestation")
        graph.add_edge("attestation", END)
        return graph.compile()

    def _initialize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"test_state": {"phase": TestPhase.INIT.value, "vehicleId": state.get("vehicleId", "FUTAWA-V-0001"), "completionPct": 0}}

    def _dyno(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_dyno_run(state)

    def _emissions(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_emissions_test(state)

    def _sound(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_sound_test(state)

    def _abs(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_abs_function_test(state)

    def _road(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_road_test(state)

    def _attestation(self, state: dict[str, Any]) -> dict[str, Any]:
        return transition_to_attestation_emitted(state)

    def solve(self, input_state: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("futawa R0 scaffold: activate via Council ADR-2605261345 post-ratification")


__all__ = ["MotoTestDynoRoadCell"]
