from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotServiceState(TypedDict):
    service_type: str
    validation_checks: List[str]
    is_compliant: bool

def validate_service(state: RobotServiceState) -> RobotServiceState:
    if state['service_type'] in ['maintenance', 'calibration']:
        state['validation_checks'].append('ISO_10218_VERIFIED')
        state['is_compliant'] = True
    return state

def integrate_system(state: RobotServiceState) -> RobotServiceState:
    if state['is_compliant']:
        state['validation_checks'].append('SYSTEM_INTEGRATION_SUCCESS')
    return state

graph = StateGraph(RobotServiceState)
graph.add_node('validate', validate_service)
graph.add_node('integrate', integrate_system)
graph.add_edge('validate', 'integrate')
graph.add_edge('integrate', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'service_type': "",
    'validation_checks': [],
    'is_compliant': False
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
