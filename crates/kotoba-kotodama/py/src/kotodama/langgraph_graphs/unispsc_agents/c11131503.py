from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MetalPowderState(TypedDict):
    material_id: str
    composition_check: bool
    safety_clearance: bool
    quality_score: float
    steps: List[str]

def validate_composition(state: MetalPowderState):
    # Simulate spectroscopic analysis for metal purity
    print(f"Validating composition for {state['material_id']}")
    return {"composition_check": True, "steps": state.get("steps", []) + ["composition_verified"]}

def perform_safety_check(state: MetalPowderState):
    # Dangerous goods verification
    print(f"Performing safety/dual-use check for {state['material_id']}")
    return {"safety_clearance": True, "steps": state.get("steps", []) + ["safety_verified"]}

builder = StateGraph(MetalPowderState)
builder.add_node("validate_composition", validate_composition)
builder.add_node("perform_safety_check", perform_safety_check)
builder.set_entry_point("validate_composition")
builder.add_edge("validate_composition", "perform_safety_check")
builder.add_edge("perform_safety_check", END)

graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'composition_check': False,
    'safety_clearance': False,
    'quality_score': 0.0,
    'steps': []
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
