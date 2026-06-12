from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    batch_id: str
    purity: float
    status: str
    validation_logs: List[str]

def validate_material(state: ProcessingState) -> ProcessingState:
    if state['purity'] >= 99.9:
        state['status'] = 'COMPLIANT'
        state['validation_logs'].append('Purity check passed.')
    else:
        state['status'] = 'REJECTED'
        state['validation_logs'].append('Purity below 99.9% threshold.')
    return state

def check_inventory(state: ProcessingState) -> ProcessingState:
    if state['status'] == 'COMPLIANT':
        state['status'] = 'READY_FOR_SHIPMENT'
    return state

graph = StateGraph(ProcessingState)
graph.add_node('validate', validate_material)
graph.add_node('inventory', check_inventory)
graph.add_edge('validate', 'inventory')
graph.add_edge('inventory', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'purity': 0.0,
    'status': "",
    'validation_logs': []
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
