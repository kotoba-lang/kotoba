from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class DiagnosticState(TypedDict):
    commodity_code: str
    batch_id: str
    temperature_logs: list[float]
    status: str

def validate_cold_chain(state: DiagnosticState) -> DiagnosticState:
    avg_temp = sum(state['temperature_logs']) / len(state['temperature_logs']) if state['temperature_logs'] else 25.0
    if 2.0 <= avg_temp <= 8.0:
        state['status'] = 'COMPLIANT'
    else:
        state['status'] = 'EXCURSION_RISK'
    return state

def verify_expiry(state: DiagnosticState) -> DiagnosticState:
    if state['status'] == 'COMPLIANT':
        state['status'] = 'VALIDATED'
    return state

graph = StateGraph(DiagnosticState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('verify_expiry', verify_expiry)
graph.set_entry_point('validate_cold_chain')
graph.add_edge('validate_cold_chain', 'verify_expiry')
graph.add_edge('verify_expiry', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'batch_id': "",
    'temperature_logs': [],
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
