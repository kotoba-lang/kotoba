from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class WildlifeProcurementState(TypedDict):
    spec_data: dict
    validation_logs: Annotated[list[str], operator.add]
    status: str

def validate_health_certs(state: WildlifeProcurementState):
    spec = state['spec_data']
    logs = [f'Validating certification for {spec.get("species")}']
    if "health_cert" in spec:
        return {"validation_logs": logs, "status": "certs_validated"}
    return {"validation_logs": logs + ["Missing health certificate"], "status": "failed"}

def process_transport_logistics(state: WildlifeProcurementState):
    return {"validation_logs": ["Logistics routing optimized for live animal welfare"], "status": "ready_for_dispatch"}

graph = StateGraph(WildlifeProcurementState)
graph.add_node("validate", validate_health_certs)
graph.add_node("logistics", process_transport_logistics)
graph.add_edge("validate", "logistics")
graph.add_edge("logistics", END)
graph.set_entry_point("validate")
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_logs': [],
    'status': ""
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
