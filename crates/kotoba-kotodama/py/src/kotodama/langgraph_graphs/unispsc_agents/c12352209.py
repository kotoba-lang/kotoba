from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    batch_id: str
    purity_level: float
    validation_checks: Annotated[Sequence[str], operator.add]
    status: str

def validate_catalyst(state: CatalystState) -> CatalystState:
    checks = []
    if state['purity_level'] < 0.99:
        checks.append('FAILED_PURITY')
        status = 'REJECTED'
    else:
        checks.append('PASSED_QC')
        status = 'READY'
    return {'validation_checks': checks, 'status': status}

def prepare_logistics(state: CatalystState) -> CatalystState:
    if state['status'] == 'READY':
        return {'status': 'READY_FOR_SHIPMENT'}
    return {'status': 'LOGISTICS_PENDING'}

graph = StateGraph(CatalystState)
graph.add_node('qc', validate_catalyst)
graph.add_node('logistics', prepare_logistics)
graph.add_edge('qc', 'logistics')
graph.set_entry_point('qc')
graph.add_edge('logistics', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'purity_level': 0.0,
    'validation_checks': [],
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
