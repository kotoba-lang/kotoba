from typing import TypedDict
from langgraph.graph import StateGraph, END

class TractorProcurementState(TypedDict):
    engine_power: float
    has_safety_certification: bool
    maintenance_records_verified: bool
    approval_status: str

def validate_specs(state: TractorProcurementState):
    if state['engine_power'] > 0 and state['has_safety_certification']:
        return {'approval_status': 'COMPLIANT'}
    return {'approval_status': 'PENDING_REVIEW'}

def check_history(state: TractorProcurementState):
    if state['maintenance_records_verified']:
        return {'approval_status': 'APPROVED'}
    return {'approval_status': 'REJECTED'}

graph = StateGraph(TractorProcurementState)
graph.add_node('validate_specs', validate_specs)
graph.add_node('check_history', check_history)
graph.set_entry_point('validate_specs')
graph.add_edge('validate_specs', 'check_history')
graph.add_edge('check_history', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'engine_power': 0.0,
    'has_safety_certification': False,
    'maintenance_records_verified': False,
    'approval_status': ""
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
