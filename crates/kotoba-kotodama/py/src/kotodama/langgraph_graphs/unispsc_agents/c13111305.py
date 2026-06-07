from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class ExplosiveState(TypedDict):
    quantity: float
    destination: str
    compliance_passed: bool
    safety_check_logs: Annotated[list, operator.add]

def validate_transport_compliance(state: ExplosiveState):
    # Simulated compliance validation logic
    is_compliant = state['quantity'] < 1000 and "secured_zone" in state['destination']
    return {"compliance_passed": is_compliant, "safety_check_logs": [f"Compliance status: {is_compliant}"]}

def route_by_compliance(state: ExplosiveState):
    return "ready" if state["compliance_passed"] else END

def stage_delivery(state: ExplosiveState):
    return {"safety_check_logs": ["Delivery successfully staged and secured for transport"]}

graph = StateGraph(ExplosiveState)
graph.add_node("validate", validate_transport_compliance)
graph.add_node("ready", stage_delivery)
graph.add_edge("validate", "ready")
graph.add_conditional_edges("validate", route_by_compliance, {"ready": "ready", END: END})
graph.set_entry_point("validate")
graph.add_edge("ready", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'quantity': 0.0,
    'destination': "",
    'compliance_passed': False,
    'safety_check_logs': []
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
