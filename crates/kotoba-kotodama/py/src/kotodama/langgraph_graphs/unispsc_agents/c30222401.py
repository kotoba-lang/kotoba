from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ClinicProcurementState(TypedDict):
    facility_requirements: List[str]
    compliance_check: bool
    final_approval: bool

def validate_facility_specs(state: ClinicProcurementState):
    print('Validating clinical facility specifications...')
    state['compliance_check'] = len(state['facility_requirements']) > 0
    return state

def run_procurement_workflow(state: ClinicProcurementState):
    print('Initiating clinical equipment procurement workflow...')
    state['final_approval'] = True
    return state

graph = StateGraph(ClinicProcurementState)
graph.add_node('validate', validate_facility_specs)
graph.add_node('procure', run_procurement_workflow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'procure')
graph.add_edge('procure', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'facility_requirements': [],
    'compliance_check': False,
    'final_approval': False
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
