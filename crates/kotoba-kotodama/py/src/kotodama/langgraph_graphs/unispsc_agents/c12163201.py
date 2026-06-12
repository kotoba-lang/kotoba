from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class SemiconductorMaterialState(TypedDict):
    material_code: str
    purity_level: float
    process_compatibility_passed: bool
    safety_check_passed: bool
    validation_logs: List[str]

def validate_material_purity(state: SemiconductorMaterialState):
    # Simulate purity check
    purity = state.get("purity_level", 0.0)
    if purity >= 99.999:
        return {"validation_logs": state["validation_logs"] + ["Purity check passed (Ultra-High Purity)"]}
    return {"validation_logs": state["validation_logs"] + ["Purity check failed"]}

def check_safety_protocols(state: SemiconductorMaterialState):
    # Simulate hazard mitigation check
    return {"safety_check_passed": True, "validation_logs": state["validation_logs"] + ["Safety protocols verified for hazardous gas"]}

def compile_graph():
    workflow = StateGraph(SemiconductorMaterialState)
    workflow.add_node("validate_purity", validate_material_purity)
    workflow.add_node("check_safety", check_safety_protocols)
    workflow.set_entry_point("validate_purity")
    workflow.add_edge("validate_purity", "check_safety")
    workflow.add_edge("check_safety", END)
    return workflow.compile()

graph = compile_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_code': "",
    'purity_level': 0.0,
    'process_compatibility_passed': False,
    'safety_check_passed': False,
    'validation_logs': []
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
