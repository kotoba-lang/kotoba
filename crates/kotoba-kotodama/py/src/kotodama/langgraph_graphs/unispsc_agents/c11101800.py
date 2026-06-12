from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    commodity_id: str
    purity_grade: float
    safety_check_passed: bool
    compliance_logs: List[str]

def validate_chemical_purity(state: ChemicalProcurementState) -> ChemicalProcurementState:
    if state['purity_grade'] < 0.99:
        state['compliance_logs'].append('Low purity: rejected')
        state['safety_check_passed'] = False
    else:
        state['compliance_logs'].append('Purity validated')
    return state

def check_regulatory_compliance(state: ChemicalProcurementState) -> ChemicalProcurementState:
    state['compliance_logs'].append('Regulatory checks completed')
    state['safety_check_passed'] = True
    return state

builder = StateGraph(ChemicalProcurementState)
builder.add_node('purity_check', validate_chemical_purity)
builder.add_node('regulatory_check', check_regulatory_compliance)
builder.add_edge('purity_check', 'regulatory_check')
builder.add_edge('regulatory_check', END)
builder.set_entry_point('purity_check')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_id': "",
    'purity_grade': 0.0,
    'safety_check_passed': False,
    'compliance_logs': []
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
