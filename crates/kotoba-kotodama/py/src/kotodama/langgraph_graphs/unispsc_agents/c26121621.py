from typing import TypedDict
from langgraph.graph import StateGraph

class KaptanCableState(TypedDict):
    spec_sheet: dict
    validation_results: dict

def validate_thermal_spec(state: KaptanCableState):
    temp_range = state['spec_sheet'].get('temp_range', 0)
    valid = temp_range >= 200
    return {'validation_results': {'thermal_pass': valid}}

def check_compliance(state: KaptanCableState):
    compliance = state['spec_sheet'].get('mil_spec_standard', False)
    return {'validation_results': {'compliance_pass': compliance}}

builder = StateGraph(KaptanCableState)
builder.add_node('thermal_val', validate_thermal_spec)
builder.add_node('compliance_val', check_compliance)
builder.set_entry_point('thermal_val')
builder.add_edge('thermal_val', 'compliance_val')
builder.add_edge('compliance_val', '__end__')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_sheet': {},
    'validation_results': {}
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
