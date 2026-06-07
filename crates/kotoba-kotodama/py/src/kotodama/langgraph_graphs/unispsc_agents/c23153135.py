from typing import TypedDict, Annotated, List
import operator
from langgraph.graph import StateGraph, END

class ActuatorState(TypedDict):
    actuator_id: str
    torque_rating: float
    status: str
    validation_log: Annotated[List[str], operator.add]

def validate_torque(state: ActuatorState):
    log = []
    if state['torque_rating'] <= 0:
        log.append('Invalid torque rating detected')
        return {'status': 'FAILED', 'validation_log': log}
    log.append('Torque rating validated')
    return {'status': 'VALIDATED', 'validation_log': log}

def perform_lifecycle_check(state: ActuatorState):
    log = ['Lifecycle safety check performed']
    return {'validation_log': log}

graph = StateGraph(ActuatorState)
graph.add_node('validate', validate_torque)
graph.add_node('lifecycle', perform_lifecycle_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'lifecycle')
graph.add_edge('lifecycle', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'actuator_id': "",
    'torque_rating': 0.0,
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
