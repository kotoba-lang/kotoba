from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class HydraulicState(TypedDict):
    spec_sheet_id: str
    pressure_validated: bool
    compliance_passed: bool
    workflow_log: List[str]

def validate_technical_specs(state: HydraulicState):
    # Simulate CAD/Spec validation for Hydraulic Cylinders
    state['pressure_validated'] = True
    state['workflow_log'].append('Validation: Technical specs and pressure ratings verified.')
    return state

def check_regulatory_compliance(state: HydraulicState):
    # Simulate Export Control and Safety checks
    state['compliance_passed'] = True
    state['workflow_log'].append('Compliance: Dual-use export control checks completed.')
    return state

graph = StateGraph(HydraulicState)
graph.add_node('validate', validate_technical_specs)
graph.add_node('compliance', check_regulatory_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)

# Compile the graph
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_sheet_id': "",
    'pressure_validated': False,
    'compliance_passed': False,
    'workflow_log': []
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
