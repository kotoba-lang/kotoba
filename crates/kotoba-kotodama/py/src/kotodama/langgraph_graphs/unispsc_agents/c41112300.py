from langgraph.graph import StateGraph, END
from typing import TypedDict
class ProcurementState(TypedDict):
    spec: dict
    validated: bool
    error: str
def validate_specs(state: ProcurementState):
    required = ['measurement_range', 'accuracy_tolerance']
    if all(k in state['spec'] for k in required):
        return {'validated': True}
    return {'validated': False, 'error': 'Missing critical technical parameters'}
def check_calibration(state: ProcurementState):
    if state['spec'].get('calibration_certificate'):
        return {'validated': True}
    return {'validated': False, 'error': 'Calibration certificate required for compliance'}
graph = StateGraph(ProcurementState)
graph.add_node('val', validate_specs)
graph.add_node('cal', check_calibration)
graph.set_entry_point('val')
graph.add_edge('val', 'cal')
graph.add_edge('cal', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec': {},
    'validated': False,
    'error': ""
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
