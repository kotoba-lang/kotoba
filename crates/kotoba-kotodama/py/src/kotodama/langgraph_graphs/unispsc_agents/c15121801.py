from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class ConduitState(TypedDict):
    material_spec: str
    pressure_rating: float
    inspection_status: List[str]
    is_compliant: bool

def validate_material(state: ConduitState) -> ConduitState:
    if "steel" in state["material_spec"].lower():
        state["inspection_status"].append("Material validated: Metal")
    return state

def check_pressure(state: ConduitState) -> ConduitState:
    if state["pressure_rating"] > 1.0:
        state["inspection_status"].append("Pressure rating passed")
        state["is_compliant"] = True
    else:
        state["is_compliant"] = False
    return state

workflow = StateGraph(ConduitState)
workflow.add_node("validate", validate_material)
workflow.add_node("pressure", check_pressure)
workflow.set_entry_point("validate")
workflow.add_edge("validate", "pressure")
workflow.add_edge("pressure", END)

graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_spec': "",
    'pressure_rating': 0.0,
    'inspection_status': [],
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
