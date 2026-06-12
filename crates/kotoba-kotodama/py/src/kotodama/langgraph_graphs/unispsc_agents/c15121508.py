from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AerospaceMaterialState(TypedDict):
    material_id: str
    spec_requirements: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_material_specs(state: AerospaceMaterialState):
    # Simulate validation logic for AMS alloy compliance
    logs = [f"Validating material {state['material_id']} against aerospace standards."]
    return {'validation_logs': logs, 'is_compliant': True}

def check_certification(state: AerospaceMaterialState):
    # Verify mill certificate documentation completeness
    logs = ["Verifying physical test reports and mill certification."]
    return {'validation_logs': logs}

builder = StateGraph(AerospaceMaterialState)
builder.add_node("validate", validate_material_specs)
builder.add_node("certify", check_certification)
builder.add_edge("validate", "certify")
builder.add_edge("certify", END)
builder.set_entry_point("validate")
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'spec_requirements': {},
    'validation_logs': [],
    'is_compliant': False
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
