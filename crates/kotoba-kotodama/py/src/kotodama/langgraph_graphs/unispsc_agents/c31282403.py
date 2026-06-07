from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    component_id: str
    material_check: bool
    clearance_status: str
    final_assembly_ready: bool

def validate_material(state: ProcessingState):
    print(f"Verifying brass grade for {state['component_id']}")
    return {"material_check": True}

def security_clearance(state: ProcessingState):
    print(f"Running dual-use export control checks for {state['component_id']}")
    return {"clearance_status": "APPROVED"}

graph = StateGraph(ProcessingState)
graph.add_node("validate_material", validate_material)
graph.add_node("security_clearance", security_clearance)
graph.set_entry_point("validate_material")
graph.add_edge("validate_material", "security_clearance")
graph.add_edge("security_clearance", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'component_id': "",
    'material_check': False,
    'clearance_status': "",
    'final_assembly_ready': False
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
