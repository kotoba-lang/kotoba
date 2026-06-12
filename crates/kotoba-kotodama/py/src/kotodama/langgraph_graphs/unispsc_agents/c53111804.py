from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ShoeProcurementState(TypedDict):
    material_specs: dict
    compliance_docs: List[str]
    approved: bool

def validate_material(state: ShoeProcurementState):
    # Business logic for checking material non-toxicity
    state['approved'] = all(m in ["Leather", "Synthetic", "Rubber"] for m in state['material_specs'])
    return state

def check_compliance(state: ShoeProcurementState):
    # Verification of safety certificates
    if len(state['compliance_docs']) < 2: state['approved'] = False
    return state

builder = StateGraph(ShoeProcurementState)
builder.add_node("validate_material", validate_material)
builder.add_node("check_compliance", check_compliance)
builder.set_entry_point("validate_material")
builder.add_edge("validate_material", "check_compliance")
builder.add_edge("check_compliance", END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_specs': {},
    'compliance_docs': [],
    'approved': False
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
