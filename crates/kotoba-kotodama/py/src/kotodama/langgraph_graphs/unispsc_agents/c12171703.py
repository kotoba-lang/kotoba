from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SilaneProcurementState(TypedDict):
    purity_check: bool
    trace_metal_level: float
    inspection_status: str
    logs: Annotated[Sequence[str], operator.add]

def validate_purity(state: SilaneProcurementState):
    is_pure = state['purity_check'] and state['trace_metal_level'] < 0.01
    return {'inspection_status': 'PASSED' if is_pure else 'REJECTED'}

def update_records(state: SilaneProcurementState):
    return {'logs': [f'Status recorded as {state["inspection_status"]}']}

graph = StateGraph(SilaneProcurementState)
graph.add_node('validate', validate_purity)
graph.add_node('record', update_records)
graph.set_entry_point('validate')
graph.add_edge('validate', 'record')
graph.add_edge('record', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_check': False,
    'trace_metal_level': 0.0,
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
