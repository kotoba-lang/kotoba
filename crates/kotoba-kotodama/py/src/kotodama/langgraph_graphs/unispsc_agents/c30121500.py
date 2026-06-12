from typing import TypedDict
from langgraph.graph import StateGraph, END

class BitumenState(TypedDict):
    spec_data: dict
    validation_result: bool
    compliant: bool

def validate_bitumen_specs(state: BitumenState):
    # Business logic for checking technical specs like flash point and penetration
    mandatory_fields = ['flash_point', 'viscosity', 'sds_verified']
    valid = all(key in state['spec_data'] for key in mandatory_fields)
    return {'validation_result': valid, 'compliant': valid}

def check_regulatory_compliance(state: BitumenState):
    # Check hazardous material transport protocols
    is_compliant = state['validation_result'] and state['spec_data'].get('hazmat_approved', False)
    return {'compliant': is_compliant}

graph = StateGraph(BitumenState)
graph.add_node('spec_validation', validate_bitumen_specs)
graph.add_node('regulatory_check', check_regulatory_compliance)
graph.set_entry_point('spec_validation')
graph.add_edge('spec_validation', 'regulatory_check')
graph.add_edge('regulatory_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_result': False,
    'compliant': False
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
