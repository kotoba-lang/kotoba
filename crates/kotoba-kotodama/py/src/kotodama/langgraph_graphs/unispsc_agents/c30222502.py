from typing import TypedDict
from langgraph.graph import StateGraph, END

class FlatSteelState(TypedDict):
    material_grade: str
    thickness: float
    width: float
    certification_verified: bool

def validate_specs(state: FlatSteelState):
    valid = state.get('material_grade') is not None and state.get('thickness') > 0
    return {'certification_verified': valid}

def route(state: FlatSteelState):
    return 'process' if state['certification_verified'] else END

def process_order(state: FlatSteelState):
    print(f'Processing flat steel order for grade: {state['material_grade']}')
    return {'certification_verified': True}

graph = StateGraph(FlatSteelState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_order)
graph.add_edge('validate', 'process')
graph.add_conditional_edges('validate', route, {'process': 'process', '__end__': END})
graph.set_entry_point('validate')
graph.set_finish_point('process')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_grade': "",
    'thickness': 0.0,
    'width': 0.0,
    'certification_verified': False
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
