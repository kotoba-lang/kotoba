from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PressBrakeState(TypedDict):
    specs: dict
    validation_errors: List[str]
    is_compliant: bool

def validate_safety_standards(state: PressBrakeState):
    standards = state['specs'].get('Safety Certification Standards', [])
    if not standards:
        state['validation_errors'].append('Missing safety certifications')
        state['is_compliant'] = False
    return state

def check_capacity(state: PressBrakeState):
    if state['specs'].get('Maximum Bending Force (kN)', 0) <= 0:
        state['validation_errors'].append('Invalid bending force')
        state['is_compliant'] = False
    return state

graph = StateGraph(PressBrakeState)
graph.add_node('validate_safety', validate_safety_standards)
graph.add_node('check_capacity', check_capacity)
graph.add_edge('validate_safety', 'check_capacity')
graph.add_edge('check_capacity', END)
graph.set_entry_point('validate_safety')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
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
