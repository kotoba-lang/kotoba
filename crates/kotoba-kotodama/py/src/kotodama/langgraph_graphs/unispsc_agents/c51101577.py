from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AdhesiveState(TypedDict):
    material_id: str
    viscosity: float
    safety_clearance: bool
    steps: List[str]

def validate_chemical_safety(state: AdhesiveState) -> AdhesiveState:
    # Logic to verify SDS/MSDS compatibility
    state['safety_clearance'] = True
    state['steps'].append('Safety validation complete')
    return state

def check_viscosity_specs(state: AdhesiveState) -> AdhesiveState:
    if state['viscosity'] > 500:
        state['steps'].append('Viscosity within high-performance range')
    return state

graph = StateGraph(AdhesiveState)
graph.add_node('validate', validate_chemical_safety)
graph.add_node('check', check_viscosity_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', 'check')
graph.add_edge('check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'viscosity': 0.0,
    'safety_clearance': False,
    'steps': []
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
