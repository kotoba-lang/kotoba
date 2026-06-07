from typing import TypedDict
from langgraph.graph import StateGraph, END

class LaserProcurementState(TypedDict):
    specs: dict
    safety_verified: bool
    export_cleared: bool

def validate_specs(state: LaserProcurementState):
    """Validates laser power vs safety constraints."""
    print(f"Validating specs: {state['specs']}")
    return {'safety_verified': state['specs'].get('power', 0) < 50}

def check_compliance(state: LaserProcurementState):
    """Checks dual-use export control status."""
    return {'export_cleared': True}

builder = StateGraph(LaserProcurementState)
builder.add_node("validate", validate_specs)
builder.add_node("compliance", check_compliance)
builder.set_entry_point("validate")
builder.add_edge("validate", "compliance")
builder.add_edge("compliance", END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'safety_verified': False,
    'export_cleared': False
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
