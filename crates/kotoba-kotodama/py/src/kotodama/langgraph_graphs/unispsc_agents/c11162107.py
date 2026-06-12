from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class LubricantState(TypedDict):
    lubricant_id: str
    viscosity: float
    safety_score: float
    approval_status: bool

def validate_viscosity(state: LubricantState) -> dict:
    return {"approval_status": state["viscosity"] > 10.0}

def check_safety(state: LubricantState) -> dict:
    return {"safety_score": 0.95 if state["approval_status"] else 0.5}

graph = StateGraph(LubricantState)
graph.add_node("validate", validate_viscosity)
graph.add_node("safety_check", check_safety)
graph.set_entry_point("validate")
graph.add_edge("validate", "safety_check")
graph.add_edge("safety_check", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'lubricant_id': "",
    'viscosity': 0.0,
    'safety_score': 0.0,
    'approval_status': False
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
