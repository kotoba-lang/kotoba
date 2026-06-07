from typing import TypedDict
from langgraph.graph import StateGraph, END

class WaterMeterState(TypedDict):
    part_number: str
    compatibility_verified: bool
    pressure_rating: float
    status: str

def verify_compatibility(state: WaterMeterState):
    state['compatibility_verified'] = state['part_number'].startswith('WM-')
    state['status'] = 'verified' if state['compatibility_verified'] else 'rejected'
    return state

def check_pressure(state: WaterMeterState):
    if state['pressure_rating'] < 10.0:
        state['status'] = 'pressure_insufficient'
    return state

graph = StateGraph(WaterMeterState)
graph.add_node('verify', verify_compatibility)
graph.add_node('pressure_check', check_pressure)
graph.set_entry_point('verify')
graph.add_edge('verify', 'pressure_check')
graph.add_edge('pressure_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'compatibility_verified': False,
    'pressure_rating': 0.0,
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
