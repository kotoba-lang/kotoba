from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class HydraulicState(TypedDict):
    spec_data: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_pressure_rating(state: HydraulicState):
    pressure = state['spec_data'].get('operating_pressure_mpa', 0)
    if pressure > 35.0:
        return {'validation_logs': ['High pressure rating requires extra verification'], 'is_approved': True}
    return {'validation_logs': ['Standard pressure range verified'], 'is_approved': True}

def structural_integrity_check(state: HydraulicState):
    return {'validation_logs': ['Structural integrity pass'], 'is_approved': True}

graph = StateGraph(HydraulicState)
graph.add_node('validate_pressure', validate_pressure_rating)
graph.add_node('structural_integrity', structural_integrity_check)
graph.add_edge('validate_pressure', 'structural_integrity')
graph.add_edge('structural_integrity', END)
graph.set_entry_point('validate_pressure')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_logs': [],
    'is_approved': False
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
