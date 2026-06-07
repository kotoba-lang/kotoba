from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class MoldState(TypedDict):
    material_specs: dict
    validation_passed: bool
    compliance_checks: List[str]

def validate_material(state: MoldState):
    purity = state['material_specs'].get('graphite_purity', 0)
    state['validation_passed'] = purity >= 99.0
    state['compliance_checks'].append('Purity Check')
    return state

def check_hazmat(state: MoldState):
    state['compliance_checks'].append('Lead Safety Protocol')
    return state

graph = StateGraph(MoldState)
graph.add_node('validate', validate_material)
graph.add_node('hazmat', check_hazmat)
graph.set_entry_point('validate')
graph.add_edge('validate', 'hazmat')
graph.add_edge('hazmat', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_specs': {},
    'validation_passed': False,
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
