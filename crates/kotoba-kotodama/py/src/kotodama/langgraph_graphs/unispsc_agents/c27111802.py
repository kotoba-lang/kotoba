from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LevelState(TypedDict):
    accuracy: float
    material: str
    needs_calibration: bool
    validation_report: List[str]

def validate_precision(state: LevelState):
    if state['accuracy'] > 1.0:
        state['validation_report'].append('Precision exceeds standard tolerance')
    return state

def check_compliance(state: LevelState):
    if state['needs_calibration']:
        state['validation_report'].append('Calibration certificate required for compliance')
    return state

graph = StateGraph(LevelState)
graph.add_node('validate_precision', validate_precision)
graph.add_node('check_compliance', check_compliance)
graph.add_edge('validate_precision', 'check_compliance')
graph.add_edge('check_compliance', END)
graph.set_entry_point('validate_precision')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'accuracy': 0.0,
    'material': "",
    'needs_calibration': False,
    'validation_report': []
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
