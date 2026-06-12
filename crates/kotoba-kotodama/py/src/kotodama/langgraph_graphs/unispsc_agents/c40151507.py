from typing import TypedDict
from langgraph.graph import StateGraph, END

class PumpState(TypedDict):
    spec_data: dict
    validation_result: bool

def validate_efficiency(state: PumpState):
    power = state['spec_data'].get('power', 0)
    flow = state['spec_data'].get('flow', 0)
    return {'validation_result': flow / power > 0.5 if power > 0 else False}

def route_by_type(state: PumpState):
    return 'process_submersible' if state['spec_data'].get('type') == 'sub' else 'process_surface'

graph = StateGraph(PumpState)
graph.add_node('validate', validate_efficiency)
graph.add_node('process_submersible', lambda x: x)
graph.add_node('process_surface', lambda x: x)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_type)
graph.add_edge('process_submersible', END)
graph.add_edge('process_surface', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_result': False
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
