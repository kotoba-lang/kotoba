from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DialysisStandState(TypedDict):
    spec_data: dict
    validation_errors: List[str]
    is_compliant: bool

def validate_load_capacity(state: DialysisStandState):
    capacity = state['spec_data'].get('load_capacity', 0)
    if capacity < 50:
        state['validation_errors'].append('Load capacity below minimum safety threshold')
    return state

def check_medical_compliance(state: DialysisStandState):
    if not state['spec_data'].get('iso_13485'):
        state['validation_errors'].append('ISO 13485 certification required')
    state['is_compliant'] = len(state['validation_errors']) == 0
    return state

graph = StateGraph(DialysisStandState)
graph.add_node('validate_capacity', validate_load_capacity)
graph.add_node('check_compliance', check_medical_compliance)
graph.set_entry_point('validate_capacity')
graph.add_edge('validate_capacity', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_errors': [],
    'is_compliant': False
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
