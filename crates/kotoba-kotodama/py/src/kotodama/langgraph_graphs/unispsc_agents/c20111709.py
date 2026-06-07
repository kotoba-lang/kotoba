from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ActuatorState(TypedDict):
    spec_data: dict
    validation_results: Annotated[Sequence[str], operator.add]
    status: str

def validate_pressure_rating(state: ActuatorState) -> ActuatorState:
    pressure = state['spec_data'].get('maximum_operating_pressure_mpa', 0)
    if pressure > 35.0:
        return {'validation_results': ['High pressure rating requires safety audit']}
    return {'validation_results': ['Pressure rating within standard limits']}

def check_material_specs(state: ActuatorState) -> ActuatorState:
    material = state['spec_data'].get('material_specification', 'unknown')
    if material == 'high-grade-steel':
        return {'validation_results': ['Material compliant with heavy-duty ops']}
    return {'validation_results': ['Material needs secondary approval']}

def build_actuator_graph():
    graph = StateGraph(ActuatorState)
    graph.add_node('validate_pressure', validate_pressure_rating)
    graph.add_node('check_material', check_material_specs)
    graph.set_entry_point('validate_pressure')
    graph.add_edge('validate_pressure', 'check_material')
    graph.add_edge('check_material', END)
    return graph.compile()

graph = build_actuator_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_results': [],
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
