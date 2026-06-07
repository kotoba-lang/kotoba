from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class FuelState(TypedDict):
    commodity: str
    volume: float
    safety_clearance: bool
    compliance_report: str

def validate_safety(state: FuelState) -> FuelState:
    # Simulate safety protocol for hazardous fuel materials
    state['safety_clearance'] = state['volume'] < 1000000.0
    return state

def generate_compliance(state: FuelState) -> FuelState:
    if state['safety_clearance']:
        state['compliance_report'] = 'CLEARED_FOR_TRANSPORT'
    else:
        state['compliance_report'] = 'REQUIRES_HAZMAT_ESCALATION'
    return state

graph = StateGraph(FuelState)
graph.add_node('safety_check', validate_safety)
graph.add_node('compliance', generate_compliance)
graph.add_edge('safety_check', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('safety_check')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity': "",
    'volume': 0.0,
    'safety_clearance': False,
    'compliance_report': ""
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
