from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    reagent_id: str
    batch_integrity: bool
    temp_log: List[float]
    status: str

def validate_cold_chain(state: ReagentState) -> ReagentState:
    # Simplified cold chain validation logic
    if all(2.0 <= t <= 8.0 for t in state['temp_log']):
        state['batch_integrity'] = True
        state['status'] = 'VALIDATED'
    else:
        state['batch_integrity'] = False
        state['status'] = 'EXCURSION_DETECTED'
    return state

def process_logistics(state: ReagentState) -> ReagentState:
    if state['batch_integrity']:
        state['status'] = 'READY_FOR_SHIPMENT'
    else:
        state['status'] = 'QUARANTINED'
    return state

builder = StateGraph(ReagentState)
builder.add_node('validate', validate_cold_chain)
builder.add_node('logistics', process_logistics)
builder.set_entry_point('validate')
builder.add_edge('validate', 'logistics')
builder.add_edge('logistics', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'reagent_id': "",
    'batch_integrity': False,
    'temp_log': [],
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
