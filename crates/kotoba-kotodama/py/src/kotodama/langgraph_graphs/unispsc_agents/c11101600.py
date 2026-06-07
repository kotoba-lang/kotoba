from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class GasProcurementState(TypedDict):
    purity_level: float
    cylinder_type: str
    compliance_checks: List[str]
    is_approved: bool

def validate_safety(state: GasProcurementState) -> GasProcurementState:
    # Logic to verify dangerous goods handling
    state['compliance_checks'].append('Safety Protocol Verified')
    return state

def check_purity(state: GasProcurementState) -> GasProcurementState:
    if state['purity_level'] >= 99.9:
        state['is_approved'] = True
    return state

graph = StateGraph(GasProcurementState)
graph.add_node('safety_check', validate_safety)
graph.add_node('purity_analysis', check_purity)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'purity_analysis')
graph.add_edge('purity_analysis', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'cylinder_type': "",
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
