from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    equipment_id: str
    sensor_data: dict
    maintenance_logs: List[str]
    status: str

def validate_sensor_data(state: RobotState) -> RobotState:
    # Simulate CAD/Sensor validation logic
    state['status'] = 'VALIDATED' if 'data' in state['sensor_data'] else 'FAILED'
    return state

def process_maintenance_workflow(state: RobotState) -> RobotState:
    if state['status'] == 'VALIDATED':
        state['maintenance_logs'].append('Predictive maintenance routine triggered.')
        state['status'] = 'COMPLETED'
    return state

builder = StateGraph(RobotState)
builder.add_node('validate', validate_sensor_data)
builder.add_node('process', process_maintenance_workflow)
builder.add_edge('validate', 'process')
builder.add_edge('process', END)
builder.set_entry_point('validate')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'equipment_id': "",
    'sensor_data': {},
    'maintenance_logs': [],
    'status': ""
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
