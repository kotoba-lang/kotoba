from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class AlloyState(TypedDict):
    material_id: str
    spec_compliance: bool
    test_results: List[str]
    validation_log: Annotated[List[str], operator.add]

def validate_composition(state: AlloyState) -> AlloyState:
    state["validation_log"].append("Validating material composition against aerospace standards.")
    return {"spec_compliance": True}

def conduct_ndt(state: AlloyState) -> AlloyState:
    state["validation_log"].append("Performing non-destructive testing for structural integrity.")
    state["test_results"].append("NDT_PASSED")
    return {}

builder = StateGraph(AlloyState)
builder.add_node("composition", validate_composition)
builder.add_node("ndt", conduct_ndt)
builder.add_edge("composition", "ndt")
builder.add_edge("ndt", END)
builder.set_entry_point("composition")
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'spec_compliance': False,
    'test_results': [],
    'validation_log': []
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
