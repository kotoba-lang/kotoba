from typing import TypedDict
from langgraph.graph import StateGraph, END

class LensGaugeState(TypedDict):
    measurement_data: dict
    validation_passed: bool
    calibration_status: bool

def validate_calibration(state: LensGaugeState):
    print('Checking calibration status...')
    state['calibration_status'] = state['measurement_data'].get('cert_id') is not None
    return state

def run_precision_validation(state: LensGaugeState):
    print('Validating radius accuracy against ISO standards...')
    state['validation_passed'] = state['measurement_data'].get('tolerance', 0.01) <= 0.05
    return state

graph = StateGraph(LensGaugeState)
graph.add_node('verify_calib', validate_calibration)
graph.add_node('compute_accuracy', run_precision_validation)
graph.set_entry_point('verify_calib')
graph.add_edge('verify_calib', 'compute_accuracy')
graph.add_edge('compute_accuracy', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'measurement_data': {},
    'validation_passed': False,
    'calibration_status': False
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
