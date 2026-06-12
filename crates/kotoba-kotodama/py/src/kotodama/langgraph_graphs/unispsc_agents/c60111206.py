from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DecorState(TypedDict):
    material: str
    glitter_retention: float
    compliant: bool

def validate_safety(state: DecorState) -> DecorState:
    state['compliant'] = state['material'] == 'non-toxic' and state['glitter_retention'] > 0.9
    return state

def route_by_compliance(state: DecorState) -> str:
    return 'process' if state['compliant'] else END

def finalize_procurement(state: DecorState) -> DecorState:
    print('Procurement finalized for decoration materials')
    return state

graph = StateGraph(DecorState)
graph.add_node('validate', validate_safety)
graph.add_node('process', finalize_procurement)
graph.add_edge('validate', 'process')
graph.set_entry_point('validate')
graph.set_finish_point('process')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material': "",
    'glitter_retention': 0.0,
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
