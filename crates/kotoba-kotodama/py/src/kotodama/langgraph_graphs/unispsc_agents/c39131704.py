import operator
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class CableTrayState(TypedDict):
    spec_requirements: dict
    validation_errors: Annotated[list, operator.add]
    is_compliant: bool

def validate_load_capacity(state: CableTrayState):
    errors = []
    if state['spec_requirements'].get('load', 0) < 500:
        errors.append('Load capacity below industrial safety threshold.')
    return {'validation_errors': errors}

def check_compliance(state: CableTrayState):
    is_valid = len(state['validation_errors']) == 0
    return {'is_compliant': is_valid}

graph = StateGraph(CableTrayState)
graph.add_node('validate_load', validate_load_capacity)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate_load')
graph.add_edge('validate_load', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_requirements': {},
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
