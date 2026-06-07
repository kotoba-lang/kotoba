from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class RNAProcurementState(TypedDict):
    spec_requirements: dict
    validation_status: str
    shipping_conditions: str

def validate_purity(state: RNAProcurementState):
    purity = state['spec_requirements'].get('purity_ratio', 0)
    status = 'APPROVED' if 1.8 <= purity <= 2.2 else 'REJECTED'
    return {'validation_status': status}

def check_temp(state: RNAProcurementState):
    temp = state['spec_requirements'].get('storage_temperature', 0)
    shipping = 'COLD_CHAIN_REQUIRED' if temp <= -20 else 'DRY_ICE_REQUIRED'
    return {'shipping_conditions': shipping}

graph = StateGraph(RNAProcurementState)
graph.add_node('validate', validate_purity)
graph.add_node('shipping', check_temp)
graph.set_entry_point('validate')
graph.add_edge('validate', 'shipping')
graph.add_edge('shipping', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_requirements': {},
    'validation_status': "",
    'shipping_conditions': ""
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
