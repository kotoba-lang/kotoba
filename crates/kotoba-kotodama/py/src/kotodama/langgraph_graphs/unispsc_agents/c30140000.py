from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class InsulationState(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_log: List[str]

def validate_thermal_specs(state: InsulationState):
    conductivity = state['spec_data'].get('thermal_conductivity', 1.0)
    compliant = conductivity < 0.05
    return {'is_compliant': compliant, 'validation_log': ['Thermal check passed' if compliant else 'High conductivity detected']}

def check_fire_rating(state: InsulationState):
    rating = state['spec_data'].get('fire_rating', 'None')
    return {'validation_log': state['validation_log'] + [f'Fire rating verified: {rating}']}

graph = StateGraph(InsulationState)
graph.add_node('validate_thermal', validate_thermal_specs)
graph.add_node('check_fire', check_fire_rating)
graph.set_entry_point('validate_thermal')
graph.add_edge('validate_thermal', 'check_fire')
graph.add_edge('check_fire', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'is_compliant': False,
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
