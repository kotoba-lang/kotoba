from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ResinProcessingState(TypedDict):
    resin_id: str
    purity_level: float
    safety_check_passed: bool
    compliance_tags: List[str]
    steps_completed: List[str]

def validate_purity(state: ResinProcessingState):
    passed = state['purity_level'] >= 99.5
    return {"safety_check_passed": passed, "steps_completed": state['steps_completed'] + ["purity_check"]}

def route_by_safety(state: ResinProcessingState):
    return "compliant_flow" if state['safety_check_passed'] else END

def perform_processing(state: ResinProcessingState):
    return {"steps_completed": state['steps_completed'] + ["chemical_processing_complete"]}

graph = StateGraph(ResinProcessingState)
graph.add_node("validate", validate_purity)
graph.add_node("process", perform_processing)
graph.add_edge("validate", "process")
graph.add_edge("process", END)
graph.set_entry_point("validate")
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'resin_id': "",
    'purity_level': 0.0,
    'safety_check_passed': False,
    'compliance_tags': [],
    'steps_completed': []
}


class _DefaultsWrapper2605231330:
    """Pre-fills missing TypedDict fields before delegating to the compiled graph."""

    __slots__ = ("_inner", "_defaults")

    def __init__(self, inner, defaults):
        self._inner = inner
        self._defaults = defaults

    def _merge(self, input_state):
        if not isinstance(input_state, dict):
            return input_state
        merged = dict(self._defaults)
        merged.update(input_state)
        return merged

    def invoke(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            return self._inner.invoke(merged, **kwargs)
        return self._inner.invoke(merged, config=config, **kwargs)

    async def ainvoke(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            return await self._inner.ainvoke(merged, **kwargs)
        return await self._inner.ainvoke(merged, config=config, **kwargs)

    def stream(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            return self._inner.stream(merged, **kwargs)
        return self._inner.stream(merged, config=config, **kwargs)

    async def astream(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            async for chunk in self._inner.astream(merged, **kwargs):
                yield chunk
            return
        async for chunk in self._inner.astream(merged, config=config, **kwargs):
            yield chunk

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_inner"), name)


graph = _DefaultsWrapper2605231330(graph, _DEFAULTS_2605231330)
