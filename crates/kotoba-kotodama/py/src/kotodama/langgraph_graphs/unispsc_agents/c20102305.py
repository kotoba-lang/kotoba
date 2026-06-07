from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class MiningComponentState(TypedDict):
    component_id: str
    material_data: Dict[str, Any]
    validation_results: List[str]
    approved: bool

def validate_material_specs(state: MiningComponentState) -> MiningComponentState:
    material = state.get("material_data", {})
    hardness = material.get("hardness", 0)
    if hardness > 50:
        state["validation_results"].append("Hardness within acceptable range.")
    else:
        state["validation_results"].append("Hardness check failed.")
    return state

def check_compliance(state: MiningComponentState) -> MiningComponentState:
    state["approved"] = "Hardness check failed." not in state["validation_results"]
    return state

graph = StateGraph(MiningComponentState)
graph.add_node("validate", validate_material_specs)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'component_id': "",
    'material_data': {},
    'validation_results': [],
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
