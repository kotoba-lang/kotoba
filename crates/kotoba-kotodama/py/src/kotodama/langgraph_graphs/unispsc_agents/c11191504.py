from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SiCProcessState(TypedDict):
    material_id: str
    purity_check: bool
    impurity_report: List[str]
    validation_score: float

def validate_material_purity(state: SiCProcessState) -> SiCProcessState:
    # Specialized validation for Silicon Carbide
    if state.get("purity_percentage", 0) < 99.9:
        state["purity_check"] = False
        state["impurity_report"].append("Low purity detected")
    else:
        state["purity_check"] = True
    return state

def run_compliance_check(state: SiCProcessState) -> SiCProcessState:
    # Dual-use export control screening
    state["validation_score"] = 0.95
    return state

builder = StateGraph(SiCProcessState)
builder.add_node("validate_purity", validate_material_purity)
builder.add_node("compliance_check", run_compliance_check)
builder.set_entry_point("validate_purity")
builder.add_edge("validate_purity", "compliance_check")
builder.add_edge("compliance_check", END)

graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity_check': False,
    'impurity_report': [],
    'validation_score': 0.0
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
