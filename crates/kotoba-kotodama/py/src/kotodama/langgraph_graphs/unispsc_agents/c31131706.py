import operator
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    part_specs: dict
    validation_logs: Annotated[List[str], operator.add]
    is_approved: bool

def validate_materials(state: ForgingState):
    alloy = state['part_specs'].get('alloy', 'Unknown')
    log = f"Validated alloy composition stability for {alloy}"
    return {'validation_logs': [log], 'is_approved': True}

def check_dimensional_compliance(state: ForgingState):
    tolerance = state['part_specs'].get('tolerance', 0.0)
    status = tolerance <= 0.05
    return {'validation_logs': [f"Dimensional check result: {status}"], 'is_approved': status}

graph = StateGraph(ForgingState)
graph.add_node("material_check", validate_materials)
graph.add_node("dim_check", check_dimensional_compliance)
graph.set_entry_point("material_check")
graph.add_edge("material_check", "dim_check")
graph.add_edge("dim_check", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_specs': {},
    'validation_logs': [],
    'is_approved': False
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
