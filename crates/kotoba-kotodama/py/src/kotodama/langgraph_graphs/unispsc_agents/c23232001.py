from typing import TypedDict
from langgraph.graph import StateGraph, END

class MetalMachineryState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_safety_certs(state: MetalMachineryState):
    certs = state['spec_data'].get('safety_certs', [])
    is_valid = len(certs) > 0
    return {'validation_results': [f'Cert validation: {is_valid}'], 'is_compliant': is_valid}

def check_voltage(state: MetalMachineryState):
    voltage = state['spec_data'].get('voltage', 0)
    valid = 110 <= voltage <= 480
    return {'validation_results': state['validation_results'] + [f'Voltage {voltage} valid: {valid}']}

graph = StateGraph(MetalMachineryState)
graph.add_node('safety_check', validate_safety_certs)
graph.add_node('voltage_check', check_voltage)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'voltage_check')
graph.add_edge('voltage_check', END)
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
