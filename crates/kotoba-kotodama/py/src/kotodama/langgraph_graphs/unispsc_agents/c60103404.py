from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class GeoGuideState(TypedDict):
    guide_id: str
    data_accuracy_verified: bool
    is_current_edition: bool
    validation_logs: List[str]

def verify_geodata(state: GeoGuideState):
    # Simulate verification of geographic data against current datasets
    state['data_accuracy_verified'] = True
    state['validation_logs'].append('Data verified using WGS84 standards.')
    return state

def check_edition(state: GeoGuideState):
    # Business logic for confirming the publication currency
    state['is_current_edition'] = True
    return state

builder = StateGraph(GeoGuideState)
builder.add_node('verify', verify_geodata)
builder.add_node('check', check_edition)
builder.set_entry_point('verify')
builder.add_edge('verify', 'check')
builder.add_edge('check', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'guide_id': "",
    'data_accuracy_verified': False,
    'is_current_edition': False,
    'validation_logs': []
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
