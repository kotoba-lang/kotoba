from langgraph.graph import StateGraph, END
from typing import TypedDict

class TrapezeState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_load_capacity(state: TrapezeState):
    load = state['spec_data'].get('load_capacity', 0)
    is_valid = load >= 150  # Standard clinical requirement
    return {'validated': is_valid, 'error_log': [] if is_valid else ['Insufficient load capacity']}

def check_compatibility(state: TrapezeState):
    compatible = state['spec_data'].get('bed_frame_fit', False)
    return {'validated': state['validated'] and compatible}

graph = StateGraph(TrapezeState)
graph.add_node('validate', validate_load_capacity)
graph.add_node('check_fit', check_compatibility)
graph.set_entry_point('validate')
graph.add_edge('validate', 'check_fit')
graph.add_edge('check_fit', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validated': False,
    'error_log': []
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
