from typing import TypedDict
from langgraph.graph import StateGraph, END

class BinderState(TypedDict):
    material_type: str
    spec_compliant: bool
    vendor_rating: float

def validate_specs(state: BinderState):
    is_compliant = state['material_type'] in ['steel', 'plastic'] and state['vendor_rating'] > 3.0
    return {'spec_compliant': is_compliant}

def process_procurement(state: BinderState):
    return {'spec_compliant': True}

graph_builder = StateGraph(BinderState)
graph_builder.add_node('validation', validate_specs)
graph_builder.add_node('procurement', process_procurement)
graph_builder.add_edge('validation', 'procurement')
graph_builder.add_edge('procurement', END)
graph_builder.set_entry_point('validation')
graph = graph_builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_type': "",
    'spec_compliant': False,
    'vendor_rating': 0.0
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
