from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CoalProcurementState(TypedDict):
    spec_data: dict
    inspection_result: bool
    approval_status: str

def validate_coal_quality(state: CoalProcurementState) -> CoalProcurementState:
    spec = state['spec_data']
    # Example logic: ash content check
    is_valid = spec.get('ash_content_percent', 100) < 15.0
    return {'inspection_result': is_valid}

def process_approval(state: CoalProcurementState) -> CoalProcurementState:
    if state.get('inspection_result'):
        return {'approval_status': 'APPROVED'}
    return {'approval_status': 'REJECTED_QUALITY_FAIL'}

graph = StateGraph(CoalProcurementState)
graph.add_node('validate', validate_coal_quality)
graph.add_node('approve', process_approval)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'inspection_result': False,
    'approval_status': ""
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
