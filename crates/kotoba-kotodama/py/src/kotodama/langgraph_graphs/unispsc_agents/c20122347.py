from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class ActuatorState(TypedDict):
    spec_id: str
    torque_requirements: float
    precision_level: float
    status: str
    validation_log: List[str]

def validate_torque(state: ActuatorState) -> ActuatorState:
    if state['torque_requirements'] > 0:
        state['validation_log'].append('Torque validated')
    return state

def validate_precision(state: ActuatorState) -> ActuatorState:
    if state['precision_level'] < 0.01:
        state['validation_log'].append('Precision validated')
    state['status'] = 'COMPLETED'
    return state

graph = StateGraph(ActuatorState)
graph.add_node('torque_check', validate_torque)
graph.add_node('precision_check', validate_precision)
graph.set_entry_point('torque_check')
graph.add_edge('torque_check', 'precision_check')
graph.add_edge('precision_check', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_id': "",
    'torque_requirements': 0.0,
    'precision_level': 0.0,
    'status': "",
    'validation_log': []
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
