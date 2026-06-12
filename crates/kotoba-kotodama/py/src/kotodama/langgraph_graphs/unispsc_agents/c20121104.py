from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ActuatorState(TypedDict):
    actuator_id: str
    torque_requirements: float
    validation_passed: bool
    logs: Annotated[List[str], add_messages]

def validate_specs(state: ActuatorState):
    # Simulate CAD/Engineering Spec Validation
    is_valid = state['torque_requirements'] > 0
    return {'validation_passed': is_valid, 'logs': ['Spec validation complete.']}

def hardware_check(state: ActuatorState):
    return {'logs': ['Hardware stress test simulation finished.']}

def deploy_actuator(state: ActuatorState):
    return {'logs': ['Actuator ready for integration.']}

builder = StateGraph(ActuatorState)
builder.add_node('validate', validate_specs)
builder.add_node('hw_check', hardware_check)
builder.add_node('deploy', deploy_actuator)

builder.set_entry_point('validate')
builder.add_edge('validate', 'hw_check')
builder.add_edge('hw_check', 'deploy')
builder.add_edge('deploy', END)

graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'actuator_id': "",
    'torque_requirements': 0.0,
    'validation_passed': False,
    'logs': []
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
