from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class SealProcurementState(TypedDict):
    part_number: str
    material_spec: str
    pressure_rating: float
    validation_status: str
    approval_path: str

def validate_specs(state: SealProcurementState):
    # Simulate engineering validation for seal specs
    if state['pressure_rating'] > 50.0:
        return {'validation_status': 'APPROVED', 'approval_path': 'FAST_TRACK'}
    return {'validation_status': 'PENDING_REVIEW', 'approval_path': 'ENGINEERING_AUDIT'}

def perform_quality_check(state: SealProcurementState):
    return {'validation_status': 'QUALITY_VERIFIED'}

graph = StateGraph(SealProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('quality_check', perform_quality_check)
graph.add_edge('validate', 'quality_check')
graph.add_edge('quality_check', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'material_spec': "",
    'pressure_rating': 0.0,
    'validation_status': "",
    'approval_path': ""
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
