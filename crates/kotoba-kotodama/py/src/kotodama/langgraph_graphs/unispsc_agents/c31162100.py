from typing import TypedDict
from langgraph.graph import StateGraph, END

class AnchorState(TypedDict):
    spec: dict
    validation_errors: list
    is_approved: bool

def validate_load_capacity(state: AnchorState):
    capacity = state['spec'].get('load_capacity', 0)
    if capacity <= 0:
        state['validation_errors'].append('Invalid load capacity')
    return {'is_approved': len(state['validation_errors']) == 0}

def structural_compliance_check(state: AnchorState):
    material = state['spec'].get('material', '')
    if not material:
        state['validation_errors'].append('Missing material specification')
    return {'is_approved': len(state['validation_errors']) == 0}

graph = StateGraph(AnchorState)
graph.add_node('validate_specs', validate_load_capacity)
graph.add_node('compliance_check', structural_compliance_check)
graph.set_entry_point('validate_specs')
graph.add_edge('validate_specs', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec': {},
    'validation_errors': [],
    'is_approved': False
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
