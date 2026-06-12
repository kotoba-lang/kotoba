from typing import TypedDict
from langgraph.graph import StateGraph, END

class WasherState(TypedDict):
    spec: dict
    validated: bool

def validate_dimension(state: WasherState):
    s = state['spec']
    valid = 'outer_diameter' in s and 'inner_diameter' in s and s['outer_diameter'] > s['inner_diameter']
    return {'validated': valid}

def check_compliance(state: WasherState):
    return {'validated': state['validated'] and state['spec'].get('standard') is not None}

graph = StateGraph(WasherState)
graph.add_node('dimension_check', validate_dimension)
graph.add_node('compliance_check', check_compliance)
graph.set_entry_point('dimension_check')
graph.add_edge('dimension_check', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec': {},
    'validated': False
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
