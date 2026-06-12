from typing import TypedDict
from langgraph.graph import StateGraph, END

class WireState(TypedDict):
    spec_sheet: dict
    validated: bool
    safety_check: bool

def validate_asbestos_safety(state: WireState):
    content = state['spec_sheet'].get('asbestos_content', 0)
    return {'safety_check': content < 0.1}

def validate_electrical_specs(state: WireState):
    temp_rating = state['spec_sheet'].get('temp_rating', 0)
    return {'validated': temp_rating >= 200}

graph = StateGraph(WireState)
graph.add_node('safety', validate_asbestos_safety)
graph.add_node('electrical', validate_electrical_specs)
graph.set_entry_point('safety')
graph.add_edge('safety', 'electrical')
graph.add_edge('electrical', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_sheet': {},
    'validated': False,
    'safety_check': False
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
