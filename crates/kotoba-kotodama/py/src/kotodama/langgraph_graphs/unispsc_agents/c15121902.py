from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class WeldingSupplyState(TypedDict):
    material_code: str
    spec_compliance: bool
    safety_check_passed: bool
    inspection_steps: Annotated[List[str], operator.add]

def validate_material_spec(state: WeldingSupplyState):
    print(f"Validating metallurgy for {state['material_code']}")
    return {"spec_compliance": True, "inspection_steps": ["chemical_analysis_complete"]}

def perform_safety_risk_check(state: WeldingSupplyState):
    print("Running export and hazard control checks")
    return {"safety_check_passed": True, "inspection_steps": ["dual_use_clearance"]}

builder = StateGraph(WeldingSupplyState)
builder.add_node("validate", validate_material_spec)
builder.add_node("safety", perform_safety_risk_check)
builder.set_entry_point("validate")
builder.add_edge("validate", "safety")
builder.add_edge("safety", END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_code': "",
    'spec_compliance': False,
    'safety_check_passed': False,
    'inspection_steps': []
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
