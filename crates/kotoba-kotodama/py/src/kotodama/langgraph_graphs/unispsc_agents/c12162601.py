from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AluminumState(TypedDict):
    purity: float
    trace_metals: dict
    approved: bool
    logs: Annotated[Sequence[str], operator.add]

def validate_purity(state: AluminumState) -> AluminumState:
    is_valid = state['purity'] >= 99.9
    return {'approved': is_valid, 'logs': ['Purity check completed']}

def check_trace_metals(state: AluminumState) -> AluminumState:
    metals = state.get('trace_metals', {})
    risk = any(val > 0.01 for val in metals.values())
    return {'approved': not risk and state['approved'], 'logs': ['Metal analysis completed']}

graph = StateGraph(AluminumState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_trace_metals', check_trace_metals)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_trace_metals')
graph.add_edge('check_trace_metals', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'trace_metals': {},
    'approved': False,
    'logs': []
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
