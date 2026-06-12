from typing import TypedDict
from langgraph.graph import StateGraph, END

class GroundingState(TypedDict):
    material_type: str
    compliance_check: bool
    torque_requirements: float

def validate_specs(state: GroundingState) -> GroundingState:
    # Logic to verify electrical conductivity standards
    state['compliance_check'] = True if state['material_type'] == 'copper-alloy' else False
    return state

def check_torque(state: GroundingState) -> GroundingState:
    # Logic to validate torque specs for grounding integrity
    return state

builder = StateGraph(GroundingState)
builder.add_node('validate', validate_specs)
builder.add_node('torque', check_torque)
builder.set_entry_point('validate')
builder.add_edge('validate', 'torque')
builder.add_edge('torque', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_type': "",
    'compliance_check': False,
    'torque_requirements': 0.0
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
