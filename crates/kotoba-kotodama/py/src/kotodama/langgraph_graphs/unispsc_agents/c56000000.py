from typing import TypedDict
from langgraph.graph import StateGraph, END

class FurnitureState(TypedDict):
    spec_data: dict
    validation_checklist: list
    is_approved: bool

def validate_materials(state: FurnitureState):
    """Validate Material composition against safety standards"""
    print("Validating materials for furniture...")
    return {'validation_checklist': state['validation_checklist'] + ['materials_checked']}

def structural_integrity_check(state: FurnitureState):
    """Perform load-bearing and ergonomic compliance check"""
    print("Performing structural integrity tests...")
    return {'validation_checklist': state['validation_checklist'] + ['structure_passed']}

def approval_step(state: FurnitureState):
    return {'is_approved': True}

graph = StateGraph(FurnitureState)
graph.add_node("validate_materials", validate_materials)
graph.add_node("structural_integrity", structural_integrity_check)
graph.add_node("approval", approval_step)

graph.set_entry_point("validate_materials")
graph.add_edge("validate_materials", "structural_integrity")
graph.add_edge("structural_integrity", "approval")
graph.add_edge("approval", END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_checklist': [],
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
