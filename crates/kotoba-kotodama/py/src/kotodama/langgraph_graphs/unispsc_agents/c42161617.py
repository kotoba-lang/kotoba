from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class DialysisMonitorState(TypedDict):
    device_id: str
    sensor_data: dict
    compliance_check: bool
    final_approval: bool

def validate_sensor_calibration(state: DialysisMonitorState):
    # Simulate validation logic for arterial pressure sensor accuracy
    is_valid = state['sensor_data'].get('accuracy_rating', 0) > 0.95
    return {'compliance_check': is_valid}

def update_compliance_status(state: DialysisMonitorState):
    approval = state['compliance_check'] and state['device_id'].startswith('SN')
    return {'final_approval': approval}

graph = StateGraph(DialysisMonitorState)
graph.add_node('validate_sensors', validate_sensor_calibration)
graph.add_node('final_check', update_compliance_status)
graph.add_edge('validate_sensors', 'final_check')
graph.add_edge('final_check', END)
graph.set_entry_point('validate_sensors')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'device_id': "",
    'sensor_data': {},
    'compliance_check': False,
    'final_approval': False
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
