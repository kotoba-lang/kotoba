from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class StentProcurementState(TypedDict):
    order_id: str
    specifications: dict
    compliance_cleared: bool
    shipping_status: str

def validate_medical_specs(state: StentProcurementState):
    # Business logic for Coronary Stent medical device validation
    if "ISO 13485" not in state["specifications"].get("certs", []):
        return {"compliance_cleared": False}
    return {"compliance_cleared": True}

def route_by_compliance(state: StentProcurementState):
    return "process" if state["compliance_cleared"] else "reject"

graph = StateGraph(StentProcurementState)
graph.add_node("validate", validate_medical_specs)
graph.set_entry_point("validate")
graph.add_conditional_edges("validate", route_by_compliance, {"process": "process", "reject": END})
graph.add_node("process", lambda s: {"shipping_status": "Ready for cold chain"})
graph.add_edge("process", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'order_id': "",
    'specifications': {},
    'compliance_cleared': False,
    'shipping_status': ""
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
