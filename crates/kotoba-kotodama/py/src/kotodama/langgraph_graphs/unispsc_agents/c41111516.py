from typing import TypedDict
from langgraph.graph import StateGraph, END

class WeighingState(TypedDict):
    part_specs: dict
    validation_passed: bool
    calibration_required: bool

def validate_specs(state: WeighingState):
    # Business logic for verifying accessory compatibility
    state['validation_passed'] = 'model_id' in state['part_specs']
    return state

def check_calibration(state: WeighingState):
    # Logic for calibration compliance checks
    state['calibration_required'] = state['part_specs'].get('needs_cal', False)
    return state

graph = StateGraph(WeighingState)
graph.add_node('validate', validate_specs)
graph.add_node('calibration', check_calibration)
graph.set_entry_point('validate')
graph.add_edge('validate', 'calibration')
graph.add_edge('calibration', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_specs': {},
    'validation_passed': False,
    'calibration_required': False
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
