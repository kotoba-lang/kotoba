from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PolymerState(TypedDict):
    material_id: str
    purity_level: float
    safety_clearance: bool
    compliance_checks: List[str]

def validate_chemistry(state: PolymerState):
    if state['purity_level'] > 0.98:
        return {'safety_clearance': True, 'compliance_checks': ['purity_ok']}
    return {'safety_clearance': False, 'compliance_checks': ['purity_fail']}

def route_by_safety(state: PolymerState):
    return 'process' if state['safety_clearance'] else END

def process_polymer(state: PolymerState):
    return {'compliance_checks': state['compliance_checks'] + ['thermal_stability_passed']}

graph = StateGraph(PolymerState)
graph.add_node('validate', validate_chemistry)
graph.add_node('process', process_polymer)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_safety)
graph.add_edge('process', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity_level': 0.0,
    'safety_clearance': False,
    'compliance_checks': []
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
