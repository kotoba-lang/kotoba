from typing import TypedDict
from langgraph.graph import StateGraph, END

class LysateState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_lysate_specs(state: LysateState):
    specs = state['spec_data']
    required = ['purity_percentage', 'storage_temperature_requirement']
    passed = all(k in specs for k in required) and specs.get('purity_percentage', 0) > 90
    return {'validation_passed': passed, 'compliance_report': 'Validated' if passed else 'Failed QC'}

def check_cold_chain(state: LysateState):
    # Simulate cold chain logic
    return {'compliance_report': state['compliance_report'] + '; Cold chain verified.'}

graph = StateGraph(LysateState)
graph.add_node('validate', validate_lysate_specs)
graph.add_node('cold_chain', check_cold_chain)
graph.add_edge('validate', 'cold_chain')
graph.add_edge('cold_chain', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_passed': False,
    'compliance_report': ""
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
