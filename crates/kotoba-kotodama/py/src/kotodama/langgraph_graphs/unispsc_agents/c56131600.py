from typing import TypedDict
from langgraph.graph import StateGraph, END

class DisplaySpecState(TypedDict):
    dimensions: dict
    material_certified: bool
    stability_test_passed: bool
    approved: bool

def validate_dimensions(state: DisplaySpecState) -> DisplaySpecState:
    # Simplified mock validation logic for display footprint
    state['approved'] = state['dimensions'].get('height', 0) < 250
    return state

def check_safety_compliance(state: DisplaySpecState) -> DisplaySpecState:
    if state['material_certified'] and state['stability_test_passed']:
        state['approved'] = True
    else:
        state['approved'] = False
    return state

graph = StateGraph(DisplaySpecState)
graph.add_node('validate_dims', validate_dimensions)
graph.add_node('safety_check', check_safety_compliance)
graph.set_entry_point('validate_dims')
graph.add_edge('validate_dims', 'safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'dimensions': {},
    'material_certified': False,
    'stability_test_passed': False,
    'approved': False
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
