from typing import TypedDict
from langgraph.graph import StateGraph, END

class TractorState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_emissions(state: TractorState):
    emission_val = state['spec_data'].get('Engine_Emission_Rating')
    is_valid = emission_val in ['Tier4', 'StageV']
    return {'validation_results': [f'Emissions compliant: {is_valid}'], 'is_compliant': is_valid}

def check_safety(state: TractorState):
    has_rops = state['spec_data'].get('ROPS_Certification_Standard') is not None
    return {'validation_results': state['validation_results'] + [f'ROPS certified: {has_rops}']}

graph = StateGraph(TractorState)
graph.add_node('validate_emissions', validate_emissions)
graph.add_node('check_safety', check_safety)
graph.set_entry_point('validate_emissions')
graph.add_edge('validate_emissions', 'check_safety')
graph.add_edge('check_safety', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_results': [],
    'is_compliant': False
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
