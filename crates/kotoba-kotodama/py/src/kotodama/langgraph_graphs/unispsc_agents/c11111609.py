from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CoalProcurementState(TypedDict):
    carbon_content: float
    moisture: float
    status: str
    validation_log: Annotated[Sequence[str], operator.add]

def validate_coal_quality(state: CoalProcurementState):
    log = []
    if state['carbon_content'] < 80.0:
        log.append(f'Carbon content {state['carbon_content']}% below threshold')
    if state['moisture'] > 12.0:
        log.append(f'Moisture level {state['moisture']}% exceeds limit')

    new_status = 'REJECTED' if log else 'APPROVED'
    return {'status': new_status, 'validation_log': log}

def update_inventory(state: CoalProcurementState):
    return {'status': f'{state['status']}_INVENTORY_UPDATED'}

builder = StateGraph(CoalProcurementState)
builder.add_node('validate', validate_coal_quality)
builder.add_node('inventory', update_inventory)
builder.add_edge('validate', 'inventory')
builder.set_entry_point('validate')
builder.add_edge('inventory', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'carbon_content': 0.0,
    'moisture': 0.0,
    'status': "",
    'validation_log': []
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
