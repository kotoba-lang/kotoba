from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class StorageState(TypedDict):
    capacity: float
    moisture: float
    pest_free: bool
    log: List[str]

def validate_capacity(state: StorageState) -> StorageState:
    if state['capacity'] > 0:
        state['log'].append('Capacity validated.')
    return state

def check_integrity(state: StorageState) -> StorageState:
    if state['moisture'] < 12.0 and state['pest_free']:
        state['log'].append('Integrity check passed.')
    else:
        state['log'].append('Integrity alert: Check environment.')
    return state

graph = StateGraph(StorageState)
graph.add_node('capacity', validate_capacity)
graph.add_node('integrity', check_integrity)
graph.set_entry_point('capacity')
graph.add_edge('capacity', 'integrity')
graph.add_edge('integrity', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'capacity': 0.0,
    'moisture': 0.0,
    'pest_free': False,
    'log': []
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
