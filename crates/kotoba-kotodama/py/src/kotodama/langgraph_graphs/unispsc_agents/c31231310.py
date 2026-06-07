from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SteelSpec(TypedDict):
    material_grade: str
    diameter: float
    thickness: float
    compliance: bool

def validate_specs(state: SteelSpec):
    print(f"Validating grade: {state['material_grade']}")
    state['compliance'] = state['diameter'] > 0 and state['thickness'] > 0
    return state

def detect_export_risk(state: SteelSpec):
    print("Checking export controls...")
    return state

builder = StateGraph(SteelSpec)
builder.add_node("validate", validate_specs)
builder.add_node("export_check", detect_export_risk)
builder.set_entry_point("validate")
builder.add_edge("validate", "export_check")
builder.add_edge("export_check", END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_grade': "",
    'diameter': 0.0,
    'thickness': 0.0,
    'compliance': False
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
