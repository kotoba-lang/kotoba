from typing import TypedDict
from langgraph.graph import StateGraph, END

class VaccineState(TypedDict):
    batch_id: str
    temp_log: list
    is_compliant: bool

def validate_cold_chain(state: VaccineState) -> VaccineState:
    # Logic to verify temperature logs for cold chain integrity
    state['is_compliant'] = all(t < 8.0 for t in state['temp_log'])
    return state

def check_regulatory(state: VaccineState) -> VaccineState:
    # Logic for batch regulatory check
    return state

graph = StateGraph(VaccineState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('check_regulatory', check_regulatory)
graph.set_entry_point('validate_cold_chain')
graph.add_edge('validate_cold_chain', 'check_regulatory')
graph.add_edge('check_regulatory', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'temp_log': [],
    'is_compliant': False
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
