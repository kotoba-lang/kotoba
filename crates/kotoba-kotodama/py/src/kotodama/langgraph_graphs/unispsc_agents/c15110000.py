from typing import TypedDict, Annotated, List, Any
from langgraph.graph import StateGraph, END

class MineralProcurementState(TypedDict):
    material_id: str
    purity_check: float
    origin_verified: bool
    compliance_risk: List[str]
    approved: bool

def validate_material(state: MineralProcurementState) -> MineralProcurementState:
    # Specialized logic for mineral purity validation
    if state.get('purity_check', 0) < 0.99:
        state['approved'] = False
    return state

def check_compliance(state: MineralProcurementState) -> MineralProcurementState:
    # Dual-use and sanctions checks
    if not state.get('origin_verified', False):
        state['compliance_risk'].append('Origin Unverified')
    return state

def compile_procurement_graph():
    graph = StateGraph(MineralProcurementState)
    graph.add_node('validate', validate_material)
    graph.add_node('compliance', check_compliance)
    graph.set_entry_point('validate')
    graph.add_edge('validate', 'compliance')
    graph.add_edge('compliance', END)
    return graph.compile()

graph = compile_procurement_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity_check': 0.0,
    'origin_verified': False,
    'compliance_risk': [],
    'approved': False
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
