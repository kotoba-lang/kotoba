from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class GarmentState(TypedDict):
    spec_data: dict
    validation_results: Annotated[list, operator.add]

def validate_materials(state: GarmentState):
    comp = state['spec_data'].get('composition', '')
    return {'validation_results': ['Material composition checked' if comp else 'Missing composition']}

def validate_sizing(state: GarmentState):
    sizes = state['spec_data'].get('sizes', [])
    return {'validation_results': ['Sizing standards verified' if len(sizes) > 0 else 'No sizes provided']}

builder = StateGraph(GarmentState)
builder.add_node('material_check', validate_materials)
builder.add_node('size_check', validate_sizing)
builder.set_entry_point('material_check')
builder.add_edge('material_check', 'size_check')
builder.add_edge('size_check', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_results': []
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
