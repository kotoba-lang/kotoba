from typing import TypedDict
from langgraph.graph import StateGraph, END

class AircraftRibState(TypedDict):
    spec_data: dict
    validation_results: list
    is_approved: bool

def validate_structural_integrity(state: AircraftRibState):
    # Simulate NDT and material property validation logic
    state['validation_results'].append('Structural integrity verified against AMS specifications')
    return {'validation_results': state['validation_results']}

def check_compliance(state: AircraftRibState):
    # Simulate export control and regulatory compliance checks
    state['is_approved'] = True
    return {'is_approved': True}

workflow = StateGraph(AircraftRibState)
workflow.add_node('structural_check', validate_structural_integrity)
workflow.add_node('compliance_check', check_compliance)
workflow.add_edge('structural_check', 'compliance_check')
workflow.set_entry_point('structural_check')
workflow.add_edge('compliance_check', END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_results': [],
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
