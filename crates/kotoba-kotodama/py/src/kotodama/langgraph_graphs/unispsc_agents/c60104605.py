from typing import TypedDict
from langgraph.graph import StateGraph, END

class FrictionState(TypedDict):
    spec_data: dict
    validation_passed: bool
    calibration_status: str

def validate_specs(state: FrictionState):
    # Simulate CAD and component validation logic
    state['validation_passed'] = all(k in state['spec_data'] for k in ['material', 'precision'])
    print(f'Validation result: {state['validation_passed']}')
    return {'validation_passed': state['validation_passed']}

def verify_calibration(state: FrictionState):
    state['calibration_status'] = 'CERTIFIED' if state.get('validation_passed') else 'PENDING'
    return {'calibration_status': state['calibration_status']}

graph = StateGraph(FrictionState)
graph.add_node('validate', validate_specs)
graph.add_node('calibrate', verify_calibration)
graph.set_entry_point('validate')
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_passed': False,
    'calibration_status': ""
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
