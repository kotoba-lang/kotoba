from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CellState(TypedDict):
    lot_number: str
    temp_log: List[float]
    is_viable: bool

def validate_cold_chain(state: CellState) -> CellState:
    # Logic to ensure the yeast competent cells stayed below -70C
    state['is_viable'] = all(temp <= -70 for temp in state['temp_log'])
    return state

def process_qc(state: CellState) -> CellState:
    # Logic to check transformation efficiency against specifications
    return state

graph = StateGraph(CellState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('process_qc', process_qc)
graph.set_entry_point('validate_cold_chain')
graph.add_edge('validate_cold_chain', 'process_qc')
graph.add_edge('process_qc', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'lot_number': "",
    'temp_log': [],
    'is_viable': False
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
