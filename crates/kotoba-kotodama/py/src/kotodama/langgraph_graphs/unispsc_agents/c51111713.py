from typing import TypedDict
from langgraph.graph import StateGraph, END

class AlemtuzumabState(TypedDict):
    vial_barcode: str
    temperature_logs: list[float]
    verification_status: bool

def validate_cold_chain(state: AlemtuzumabState):
    avg_temp = sum(state['temperature_logs']) / len(state['temperature_logs'])
    status = 2.0 <= avg_temp <= 8.0
    return {'verification_status': status}

def verify_integrity(state: AlemtuzumabState):
    return {'verification_status': state['verification_status'] and len(state['vial_barcode']) == 12}

graph = StateGraph(AlemtuzumabState)
graph.add_node('validate_temp', validate_cold_chain)
graph.add_node('verify_code', verify_integrity)
graph.set_entry_point('validate_temp')
graph.add_edge('validate_temp', 'verify_code')
graph.add_edge('verify_code', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'vial_barcode': "",
    'temperature_logs': [],
    'verification_status': False
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
