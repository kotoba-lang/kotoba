from typing import TypedDict
from langgraph.graph import StateGraph, END

class PETUnitState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_shielding(state: PETUnitState):
    shielding = state['spec_data'].get('shielding_mm', 0)
    valid = shielding >= 10
    return {'validation_results': [f'Shielding at {shielding}mm: {valid}'], 'is_compliant': valid}

def check_regulations(state: PETUnitState):
    compliance = state['spec_data'].get('iec_60601_certified', False)
    return {'is_compliant': state['is_compliant'] and compliance}

graph = StateGraph(PETUnitState)
graph.add_node('shielding_check', validate_shielding)
graph.add_node('regulatory_check', check_regulations)
graph.set_entry_point('shielding_check')
graph.add_edge('shielding_check', 'regulatory_check')
graph.add_edge('regulatory_check', END)
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
