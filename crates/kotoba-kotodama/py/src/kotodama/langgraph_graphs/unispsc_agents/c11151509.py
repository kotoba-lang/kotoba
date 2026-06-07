from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class GasSupplyState(TypedDict):
    gas_spec: dict
    safety_check: bool
    logistics_status: str

def validate_safety_compliance(state: GasSupplyState) -> GasSupplyState:
    # Logic to verify container pressure and safety certification
    state['safety_check'] = state['gas_spec'].get('pressure', 0) < 300
    return state

def process_delivery(state: GasSupplyState) -> GasSupplyState:
    # Logic for specialized hazardous material logistics
    state['logistics_status'] = 'COMPLIANT_LOGISTICS_READY' if state['safety_check'] else 'REJECTED_SAFETY_VIOLATION'
    return state

graph = StateGraph(GasSupplyState)
graph.add_node('safety_check', validate_safety_compliance)
graph.add_node('logistics', process_delivery)
graph.add_edge('safety_check', 'logistics')
graph.add_edge('logistics', END)
graph.set_entry_point('safety_check')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'gas_spec': {},
    'safety_check': False,
    'logistics_status': ""
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
