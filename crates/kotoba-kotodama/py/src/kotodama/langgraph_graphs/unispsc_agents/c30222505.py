from typing import TypedDict
from langgraph.graph import StateGraph, END

class RetirementHomeState(TypedDict):
    facility_id: str
    compliance_score: float
    inspection_status: str

def validate_compliance(state: RetirementHomeState):
    # Simulate audit check logic for retirement facility standards
    state['compliance_score'] = 95.0
    state['inspection_status'] = 'PASSED'
    return state

def finalize_contract(state: RetirementHomeState):
    print(f'Finalizing contract for facility {state['facility_id']}')
    return state

graph = StateGraph(RetirementHomeState)
graph.add_node('audit', validate_compliance)
graph.add_node('contract', finalize_contract)
graph.add_edge('audit', 'contract')
graph.add_edge('contract', END)
graph.set_entry_point('audit')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'facility_id': "",
    'compliance_score': 0.0,
    'inspection_status': ""
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
