from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PharmaState(TypedDict):
    material_name: str
    quality_docs: List[str]
    compliance_cleared: bool

def validate_gmp(state: PharmaState):
    return {"compliance_cleared": "GMP_Certificate" in state['quality_docs']}

def route_procurement(state: PharmaState):
    return "ready" if state['compliance_cleared'] else "reject"

graph = StateGraph(PharmaState)
graph.add_node("validate", validate_gmp)
graph.add_node("ready", lambda s: {"status": "ready"})
graph.add_node("reject", lambda s: {"status": "reject"})
graph.set_entry_point("validate")
graph.add_edge("validate", "ready")
graph.add_edge("validate", "reject")
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_name': "",
    'quality_docs': [],
    'compliance_cleared': False
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
