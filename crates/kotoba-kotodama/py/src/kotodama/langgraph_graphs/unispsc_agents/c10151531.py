from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class LivestockState(TypedDict):
    product_id: str
    inspection_passed: bool
    compliance_tags: List[str]

def validate_health_cert(state: LivestockState) -> LivestockState:
    # Logic to verify health certification document
    state['inspection_passed'] = True
    state['compliance_tags'].append('certified_safe')
    return state

def log_inventory(state: LivestockState) -> LivestockState:
    # Logic to record in supply chain system
    print(f'Inventory logged for {state["product_id"]}')
    return state

graph = StateGraph(LivestockState)
graph.add_node('validate', validate_health_cert)
graph.add_node('log', log_inventory)
graph.set_entry_point('validate')
graph.add_edge('validate', 'log')
graph.add_edge('log', END)

# Compile the graph
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_id': "",
    'inspection_passed': False,
    'compliance_tags': []
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
