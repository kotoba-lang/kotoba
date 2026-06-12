from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class MetalProcurementState(TypedDict):
    purity_level: float
    origin: str
    inspection_status: str
    is_compliant: bool

def validate_purity(state: MetalProcurementState):
    state['is_compliant'] = state['purity_level'] >= 99.99
    return state

def check_compliance(state: MetalProcurementState):
    return 'compliant' if state['is_compliant'] else 'non_compliant'

def mark_approved(state: MetalProcurementState):
    state['inspection_status'] = 'APPROVED'
    return state

def mark_rejected(state: MetalProcurementState):
    state['inspection_status'] = 'REJECTED'
    return state

graph = StateGraph(MetalProcurementState)
graph.add_node('validate', validate_purity)
graph.add_node('approve', mark_approved)
graph.add_node('reject', mark_rejected)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', check_compliance, {'compliant': 'approve', 'non_compliant': 'reject'})
graph.add_edge('approve', END)
graph.add_edge('reject', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'origin': "",
    'inspection_status': "",
    'is_compliant': False
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
