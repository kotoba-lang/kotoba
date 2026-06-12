from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class MineralProcurementState(TypedDict):
    commodity_code: str
    purity_level: float
    certification_docs: List[str]
    compliance_score: float

def validate_purity(state: MineralProcurementState) -> MineralProcurementState:
    if state['purity_level'] < 0.999:
        state['compliance_score'] = 0.0
    else:
        state['compliance_score'] = 1.0
    return state

def check_export_compliance(state: MineralProcurementState) -> MineralProcurementState:
    # Logic to verify dual-use export control status
    return state

def aggregate_results(state: MineralProcurementState) -> Dict[str, Any]:
    return {'status': 'approved' if state['compliance_score'] > 0.5 else 'rejected'}

graph = StateGraph(MineralProcurementState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_export', check_export_compliance)
graph.add_node('aggregate', aggregate_results)

graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_export')
graph.add_edge('check_export', 'aggregate')
graph.add_edge('aggregate', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'purity_level': 0.0,
    'certification_docs': [],
    'compliance_score': 0.0
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
