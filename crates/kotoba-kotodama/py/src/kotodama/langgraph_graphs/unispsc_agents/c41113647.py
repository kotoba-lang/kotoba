from typing import TypedDict
from langgraph.graph import StateGraph, END

class CalibratorState(TypedDict):
    spec_data: dict
    validation_errors: list
    is_compliant: bool

def validate_frequency(state: CalibratorState):
    errors = []
    if 'accuracy' not in state['spec_data']: errors.append('Missing accuracy')
    return {'validation_errors': errors, 'is_compliant': len(errors) == 0}

def check_traceability(state: CalibratorState):
    has_cert = state['spec_data'].get('has_calibration_cert', False)
    return {'is_compliant': state['is_compliant'] and has_cert}

graph = StateGraph(CalibratorState)
graph.add_node('validate', validate_frequency)
graph.add_node('traceability', check_traceability)
graph.set_entry_point('validate')
graph.add_edge('validate', 'traceability')
graph.add_edge('traceability', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_errors': [],
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
