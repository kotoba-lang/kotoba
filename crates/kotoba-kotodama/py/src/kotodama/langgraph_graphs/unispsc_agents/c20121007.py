from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class HydraulicState(TypedDict):
    spec_data: dict
    validation_log: Annotated[list, operator.add]
    is_approved: bool

def validate_pressure_specs(state: HydraulicState):
    pressure = state['spec_data'].get('max_operating_pressure_mpa', 0)
    if pressure > 70:
        return {'validation_log': ['High pressure category: requires secondary safety review'], 'is_approved': True}
    return {'validation_log': ['Standard pressure spec verified'], 'is_approved': True}

def check_compliance(state: HydraulicState):
    if 'iso_certification_code' not in state['spec_data']:
        return {'validation_log': ['Compliance failed: ISO missing'], 'is_approved': False}
    return {'validation_log': ['Compliance verified'], 'is_approved': True}

builder = StateGraph(HydraulicState)
builder.add_node('validate_pressure', validate_pressure_specs)
builder.add_node('check_compliance', check_compliance)
builder.add_edge('validate_pressure', 'check_compliance')
builder.add_edge('check_compliance', END)
builder.set_entry_point('validate_pressure')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_log': [],
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
