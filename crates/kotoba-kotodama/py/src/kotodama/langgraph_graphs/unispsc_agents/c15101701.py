from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PipeProcessState(TypedDict):
    material_grade: str
    pressure_rating: float
    specs_verified: bool
    compliance_log: List[str]

def validate_material(state: PipeProcessState) -> PipeProcessState:
    if state['material_grade'] in ['ASTM-A53', 'ASTM-A106']:
        state['specs_verified'] = True
        state['compliance_log'].append('Material grade validated')
    else:
        state['specs_verified'] = False
        state['compliance_log'].append('Material grade unknown')
    return state

def check_pressure(state: PipeProcessState) -> PipeProcessState:
    if state['pressure_rating'] >= 10.0:
        state['compliance_log'].append('Pressure rating sufficient for high-pressure application')
    return state

graph = StateGraph(PipeProcessState)
graph.add_node('validate', validate_material)
graph.add_node('pressure_check', check_pressure)
graph.set_entry_point('validate')
graph.add_edge('validate', 'pressure_check')
graph.add_edge('pressure_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_grade': "",
    'pressure_rating': 0.0,
    'specs_verified': False,
    'compliance_log': []
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
