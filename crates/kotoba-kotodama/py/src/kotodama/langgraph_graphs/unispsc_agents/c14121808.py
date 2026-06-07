from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ProcureState(TypedDict):
    spec_data: dict
    validation_log: Annotated[Sequence[str], add_messages]

def validate_dielectric(state: ProcureState):
    spec = state['spec_data']
    if spec.get('dielectric_strength_kv', 0) < 5.0:
        return {'validation_log': ['Dielectric strength below minimum required 5.0kV']}
    return {'validation_log': ['Dielectric strength check passed']}

def check_thermal(state: ProcureState):
    spec = state['spec_data']
    if spec.get('thermal_resistance_index', 0) < 155:
        return {'validation_log': ['Thermal resistance insufficient for industrial insulation']}
    return {'validation_log': ['Thermal resilience compliant']}

graph = StateGraph(ProcureState)
graph.add_node('dielectric_check', validate_dielectric)
graph.add_node('thermal_check', check_thermal)
graph.add_edge('dielectric_check', 'thermal_check')
graph.set_entry_point('dielectric_check')
graph.add_edge('thermal_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
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
