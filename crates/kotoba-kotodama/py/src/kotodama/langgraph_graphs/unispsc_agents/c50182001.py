from typing import TypedDict
from langgraph.graph import StateGraph, END

class BakeryState(TypedDict):
    temp_log: float
    has_allergen_label: bool
    is_expired: bool

def validate_temp(state: BakeryState):
    return {"is_compliant": state["temp_log"] <= 5.0}

def check_quality(state: BakeryState):
    return {"status": "APPROVED" if not state["is_expired"] and state["has_allergen_label"] else "REJECTED"}

graph = StateGraph(BakeryState)
graph.add_node("validate_temp", validate_temp)
graph.add_node("check_quality", check_quality)
graph.add_edge("validate_temp", "check_quality")
graph.add_edge("check_quality", END)
graph.set_entry_point("validate_temp")
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'temp_log': 0.0,
    'has_allergen_label': False,
    'is_expired': False
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
