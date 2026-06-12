from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PhosphateProcurementState(TypedDict):
    commodity_code: str
    purity_level: float
    inspection_status: str
    logs: List[str]

def validate_purity(state: PhosphateProcurementState) -> PhosphateProcurementState:
    if state['purity_level'] < 99.9:
        state['logs'].append('Low purity: FAILED')
        state['inspection_status'] = 'REJECTED'
    else:
        state['logs'].append('Purity check: PASSED')
        state['inspection_status'] = 'CERTIFIED'
    return state

def route_by_status(state: PhosphateProcurementState) -> str:
    return 'process_order' if state['inspection_status'] == 'CERTIFIED' else 'end'

graph = StateGraph(PhosphateProcurementState)
graph.add_node('validate', validate_purity)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_status, {'process_order': END, 'end': END})
graph.add_edge('validate', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'purity_level': 0.0,
    'inspection_status': "",
    'logs': []
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
