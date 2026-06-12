from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ServoState(TypedDict):
    servo_id: str
    torque_spec: float
    test_results: List[dict]
    status: str

def validate_torque(state: ServoState):
    # Simulate CAD/Spec validation for 20122005 class
    if state['torque_spec'] < 5.0:
        return {'status': 'rejected_insufficient_torque'}
    return {'status': 'torque_validated'}

def perform_inspection(state: ServoState):
    # Simulate robotic hardware inspection workflow
    return {'test_results': [{'test': 'thermal_stress', 'passed': True}]}

graph = StateGraph(ServoState)
graph.add_node('validate_torque', validate_torque)
graph.add_node('perform_inspection', perform_inspection)
graph.set_entry_point('validate_torque')
graph.add_edge('validate_torque', 'perform_inspection')
graph.add_edge('perform_inspection', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'servo_id': "",
    'torque_spec': 0.0,
    'test_results': [],
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
