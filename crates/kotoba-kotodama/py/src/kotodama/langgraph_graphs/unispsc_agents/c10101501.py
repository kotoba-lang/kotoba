from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class LivestockState(TypedDict):
    animal_id: str
    health_status: str
    quarantine_verified: bool
    transport_logs: List[str]

def inspect_health(state: LivestockState) -> LivestockState:
    # Logic for health assessment
    state['health_status'] = 'certified'
    return state

def verify_quarantine(state: LivestockState) -> LivestockState:
    # Logic for quarantine compliance check
    state['quarantine_verified'] = True
    return state

def finalize_shipping(state: LivestockState) -> LivestockState:
    # Logic for transport approval
    state['transport_logs'].append('Shipping approved')
    return state

graph = StateGraph(LivestockState)
graph.add_node('inspect', inspect_health)
graph.add_node('quarantine', verify_quarantine)
graph.add_node('shipping', finalize_shipping)
graph.add_edge('inspect', 'quarantine')
graph.add_edge('quarantine', 'shipping')
graph.add_edge('shipping', END)
graph.set_entry_point('inspect')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'animal_id': "",
    'health_status': "",
    'quarantine_verified': False,
    'transport_logs': []
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
