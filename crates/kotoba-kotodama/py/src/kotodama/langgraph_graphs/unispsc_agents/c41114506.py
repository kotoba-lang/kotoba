from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class SpherometerState(TypedDict):
    serial_number: str
    calibration_date: str
    is_verified: bool
    errors: List[str]

def validate_calibration(state: SpherometerState):
    # Business logic for calibration verification
    state['is_verified'] = bool(state['calibration_date'])
    if not state['is_verified']:
        state['errors'].append('Invalid calibration date')
    return state

def generate_qc_report(state: SpherometerState):
    print(f'Generating report for {state.get('serial_number')}')
    return state

graph = StateGraph(SpherometerState)
graph.add_node('validate', validate_calibration)
graph.add_node('report', generate_qc_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'serial_number': "",
    'calibration_date': "",
    'is_verified': False,
    'errors': []
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
