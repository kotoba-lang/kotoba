from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AnimalProcurementState(TypedDict):
    animal_id: str
    health_status: str
    quarantine_clearance: bool
    log: Annotated[Sequence[str], operator.add]

def validate_health_node(state: AnimalProcurementState):
    # Simulate health check logic
    return {"health_status": "cleared", "log": [f"Health check verified for {state['animal_id']}"]}

def quarantine_node(state: AnimalProcurementState):
    # Simulate quarantine process
    return {"quarantine_clearance": True, "log": ["Quarantine protocol complete"]}

workflow = StateGraph(AnimalProcurementState)
workflow.add_node("health_check", validate_health_node)
workflow.add_node("quarantine", quarantine_node)
workflow.set_entry_point("health_check")
workflow.add_edge("health_check", "quarantine")
workflow.add_edge("quarantine", END)

graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'animal_id': "",
    'health_status': "",
    'quarantine_clearance': False,
    'log': []
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
