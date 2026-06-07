from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class LivestockState(TypedDict):
    commodity_id: str
    health_certs: Sequence[str]
    inspection_status: str
    is_cleared: bool

def validate_health_cert(state: LivestockState) -> LivestockState:
    # Logic to verify quarantine and vaccination documentation
    state['is_cleared'] = len(state['health_certs']) > 0
    state['inspection_status'] = 'CERTIFIED' if state['is_cleared'] else 'PENDING'
    return state

def route_by_clearance(state: LivestockState) -> str:
    return 'process_shipment' if state['is_cleared'] else 'request_audit'

def process_shipment(state: LivestockState) -> LivestockState:
    return state

def request_audit(state: LivestockState) -> LivestockState:
    return state

graph = StateGraph(LivestockState)
graph.add_node('validate', validate_health_cert)
graph.add_node('process_shipment', process_shipment)
graph.add_node('request_audit', request_audit)

graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_clearance)
graph.add_edge('process_shipment', END)
graph.add_edge('request_audit', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_id': "",
    'health_certs': [],
    'inspection_status': "",
    'is_cleared': False
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
