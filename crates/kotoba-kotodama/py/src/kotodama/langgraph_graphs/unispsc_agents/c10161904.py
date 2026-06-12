from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FeedProcurementState(TypedDict):
    commodity_code: str
    batch_id: str
    moisture: float
    status: str
    audit_logs: List[str]

def validate_moisture(state: FeedProcurementState) -> FeedProcurementState:
    if state['moisture'] > 14.0:
        state['status'] = 'REJECTED: High Moisture'
    else:
        state['status'] = 'PASSED: Moisture Check'
    return state

def check_certification(state: FeedProcurementState) -> FeedProcurementState:
    if 'PASSED' in state['status']:
        state['audit_logs'].append('Non-GMO certificate verified.')
    return state

graph = StateGraph(FeedProcurementState)
graph.add_node('validate_moisture', validate_moisture)
graph.add_node('check_cert', check_certification)
graph.add_edge('validate_moisture', 'check_cert')
graph.add_edge('check_cert', END)
graph.set_entry_point('validate_moisture')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'batch_id': "",
    'moisture': 0.0,
    'status': "",
    'audit_logs': []
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
