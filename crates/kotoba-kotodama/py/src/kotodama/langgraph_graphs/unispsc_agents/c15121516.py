from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class PolymerState(TypedDict):
    purity: float
    viscosity: float
    compliant: bool

def validate_polymer(state: PolymerState) -> PolymerState:
    if state['purity'] >= 99.5 and state['viscosity'] > 500:
        state['compliant'] = True
    else:
        state['compliant'] = False
    return state

def route_by_compliance(state: PolymerState) -> str:
    return 'process' if state['compliant'] else 'flag_error'

graph = StateGraph(PolymerState)
graph.add_node('validate', validate_polymer)
graph.add_node('process', lambda s: s)
graph.add_node('flag_error', lambda s: s)

graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance)
graph.add_edge('process', END)
graph.add_edge('flag_error', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'viscosity': 0.0,
    'compliant': False
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
