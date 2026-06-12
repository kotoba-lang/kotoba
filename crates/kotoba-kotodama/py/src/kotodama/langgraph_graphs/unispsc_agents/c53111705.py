from typing import TypedDict
from langgraph.graph import StateGraph, END

class InfantSlipperState(TypedDict):
    material_safety_test: bool
    slip_resistance_index: float
    compliance_report: str

def validate_material(state: InfantSlipperState):
    return {'material_safety_test': True}

def check_slip_hazard(state: InfantSlipperState):
    is_safe = state['slip_resistance_index'] >= 0.4
    return {'compliance_report': 'Passed' if is_safe else 'Failed'}

builder = StateGraph(InfantSlipperState)
builder.add_node('validate_material', validate_material)
builder.add_node('check_slip', check_slip_hazard)
builder.add_edge('validate_material', 'check_slip')
builder.add_edge('check_slip', END)
builder.set_entry_point('validate_material')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_safety_test': False,
    'slip_resistance_index': 0.0,
    'compliance_report': ""
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
