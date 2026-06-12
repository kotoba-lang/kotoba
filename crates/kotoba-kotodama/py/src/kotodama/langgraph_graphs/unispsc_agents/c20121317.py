from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotSystemState(TypedDict):
    sensor_data: dict
    maintenance_logs: List[str]
    needs_service: bool

def validate_sensor_readings(state: RobotSystemState) -> RobotSystemState:
    # Simulate high-precision sensor validation logic
    reading = state['sensor_data'].get('value', 0)
    state['needs_service'] = reading > 95
    return state

def trigger_maintenance_workflow(state: RobotSystemState) -> RobotSystemState:
    if state['needs_service']:
        state['maintenance_logs'].append('Critical threshold reached: Maintenance required')
    return state

graph = StateGraph(RobotSystemState)
graph.add_node('validate', validate_sensor_readings)
graph.add_node('maintain', trigger_maintenance_workflow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'maintain')
graph.add_edge('maintain', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'sensor_data': {},
    'maintenance_logs': [],
    'needs_service': False
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
