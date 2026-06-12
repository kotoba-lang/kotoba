from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    product_name: str
    potency: float
    storage_temp: float
    qc_passed: bool

def validate_potency(state: PharmState):
    state['qc_passed'] = 0.95 <= state['potency'] <= 1.05
    return state

def check_storage(state: PharmState):
    if state['storage_temp'] > 25:
        state['qc_passed'] = False
    return state

graph = StateGraph(PharmState)
graph.add_node('validate_potency', validate_potency)
graph.add_node('check_storage', check_storage)
graph.add_edge('validate_potency', 'check_storage')
graph.add_edge('check_storage', END)
graph.set_entry_point('validate_potency')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_name': "",
    'potency': 0.0,
    'storage_temp': 0.0,
    'qc_passed': False
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
