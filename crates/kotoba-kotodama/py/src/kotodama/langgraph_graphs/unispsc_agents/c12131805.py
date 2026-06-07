from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class GasProcessState(TypedDict):
    commodity_code: str
    purity_level: float
    safety_clearance: bool
    shipping_log: Annotated[Sequence[str], operator.add]

def validate_gas_purity(state: GasProcessState):
    is_pure = state['purity_level'] >= 99.99
    return {'safety_clearance': is_pure, 'shipping_log': ['Purity validated' if is_pure else 'Purity check failed']}

def route_shipping(state: GasProcessState):
    if state['safety_clearance']:
        return 'ship'
    return 'quarantine'

graph = StateGraph(GasProcessState)
graph.add_node('validate', validate_gas_purity)
graph.add_node('ship', lambda s: {'shipping_log': ['Dispatching high-purity gas']})
graph.add_node('quarantine', lambda s: {'shipping_log': ['Gas quarantined for safety']})
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_shipping)
graph.add_edge('ship', END)
graph.add_edge('quarantine', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'purity_level': 0.0,
    'safety_clearance': False,
    'shipping_log': []
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
