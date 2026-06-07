from typing import TypedDict
from langgraph.graph import StateGraph, END

class PlayCenterState(TypedDict):
    inspection_report: dict
    compliance_status: bool
    maintenance_plan: str

def validate_safety_standards(state: PlayCenterState):
    # Simulate CAD/Safety audit logic
    is_safe = state['inspection_report'].get('fire_rating') == 'Compliant'
    return {'compliance_status': is_safe}

def schedule_maintenance(state: PlayCenterState):
    if state.get('compliance_status'):
        return {'maintenance_plan': 'Approved: Scheduled for monthly cleaning'}
    return {'maintenance_plan': 'Rejected: Requires safety remediation'}

graph = StateGraph(PlayCenterState)
graph.add_node('validate', validate_safety_standards)
graph.add_node('schedule', schedule_maintenance)
graph.add_edge('validate', 'schedule')
graph.add_edge('schedule', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'inspection_report': {},
    'compliance_status': False,
    'maintenance_plan': ""
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
