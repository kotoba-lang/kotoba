from typing import TypedDict
from langgraph.graph import StateGraph, END

class VaccineState(TypedDict):
    lot_number: str
    temperature_logs: list
    expiry_date: str
    is_validated: bool

def validate_cold_chain(state: VaccineState):
    if all(2 <= temp <= 8 for temp in state['temperature_logs']):
        return {'is_validated': True}
    raise ValueError('Cold chain breach detected')

def check_expiry(state: VaccineState):
    # Business logic for expiry validation
    return {'is_validated': True}

graph = StateGraph(VaccineState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('check_expiry', check_expiry)
graph.add_edge('validate_cold_chain', 'check_expiry')
graph.add_edge('check_expiry', END)
graph.set_entry_point('validate_cold_chain')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'lot_number': "",
    'temperature_logs': [],
    'expiry_date': "",
    'is_validated': False
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
