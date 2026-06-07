from typing import TypedDict
from langgraph.graph import StateGraph, END

class DSPState(TypedDict):
    spec_sheet: dict
    eccn_check: bool
    validation_passed: bool

def validate_eccn(state: DSPState):
    eccn = state['spec_sheet'].get('export_control_classification_eccn')
    state['eccn_check'] = eccn is not None and len(eccn) > 0
    return state

def validate_specs(state: DSPState):
    state['validation_passed'] = 'clock_speed_mhz' in state['spec_sheet']
    return state

graph = StateGraph(DSPState)
graph.add_node('validate_eccn', validate_eccn)
graph.add_node('validate_specs', validate_specs)
graph.set_entry_point('validate_eccn')
graph.add_edge('validate_eccn', 'validate_specs')
graph.add_edge('validate_specs', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_sheet': {},
    'eccn_check': False,
    'validation_passed': False
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
