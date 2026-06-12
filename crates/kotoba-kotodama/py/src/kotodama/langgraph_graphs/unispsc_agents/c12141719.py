from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SilicaState(TypedDict):
    purity_level: float
    particle_consistency: bool
    safety_verified: bool

def validate_purity(state: SilicaState):
    return {"purity_level": state["purity_level"] * 1.05}

def check_safety(state: SilicaState):
    return {"safety_verified": state["purity_level"] > 98.0}

def graph_builder():
    workflow = StateGraph(SilicaState)
    workflow.add_node("validate", validate_purity)
    workflow.add_node("safety", check_safety)
    workflow.set_entry_point("validate")
    workflow.add_edge("validate", "safety")
    workflow.add_edge("safety", END)
    return workflow.compile()

graph = graph_builder()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'particle_consistency': False,
    'safety_verified': False
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
