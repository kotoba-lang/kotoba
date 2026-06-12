from typing import TypedDict, Annotated, Sequence, List
import operator
from langgraph.graph import StateGraph, END

class MetalProcurementState(TypedDict):
    commodity_code: str
    purity: float
    compliance_checks: Annotated[List[str], operator.add]
    is_approved: bool

def validate_purity(state: MetalProcurementState):
    # Business logic for industrial metal purity validation
    if state['purity'] >= 99.9:
        return {'compliance_checks': ['High purity verified']}
    return {'compliance_checks': ['Purity insufficient']}

def check_export_controls(state: MetalProcurementState):
    # Dual-use / Sanctions screening
    return {'compliance_checks': ['Dual-use screening complete']}

def finalize_procurement(state: MetalProcurementState):
    # Final decision logic
    is_approved = 'High purity verified' in state['compliance_checks']
    return {'is_approved': is_approved}

graph = StateGraph(MetalProcurementState)
graph.add_node('validate', validate_purity)
graph.add_node('export', check_export_controls)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'purity': 0.0,
    'compliance_checks': [],
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
