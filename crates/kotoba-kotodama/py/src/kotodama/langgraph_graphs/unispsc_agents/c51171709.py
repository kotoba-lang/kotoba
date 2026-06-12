from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    cfu_count: float
    purity_pct: float
    temp_log: list
    status: str

def validate_batch(state: ProcurementState):
    if state['cfu_count'] < 1e9: return {'status': 'rejected'}
    return {'status': 'approved'}

def graph_setup():
    graph = StateGraph(ProcurementState)
    graph.add_node('validate', validate_batch)
    graph.set_entry_point('validate')
    graph.add_edge('validate', END)
    return graph.compile()

graph = graph_setup()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'cfu_count': 0.0,
    'purity_pct': 0.0,
    'temp_log': [],
    'status': ""
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
