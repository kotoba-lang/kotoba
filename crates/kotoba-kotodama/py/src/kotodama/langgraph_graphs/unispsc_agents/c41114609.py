from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ForgingTestState(TypedDict):
    equipment_id: str
    calibration_status: bool
    test_parameters: dict
    validation_report: str

def validate_equipment(state: ForgingTestState):
    if not state.get('calibration_status'):
        return {'validation_report': 'FAILED: Calibration certificate required.'}
    return {'validation_report': 'PASSED: Ready for testing.'}

def conduct_test(state: ForgingTestState):
    return {'validation_report': 'Test conducted on ' + state['equipment_id']}

graph = StateGraph(ForgingTestState)
graph.add_node('validate', validate_equipment)
graph.add_node('test', conduct_test)
graph.set_entry_point('validate')
graph.add_edge('validate', 'test')
graph.add_edge('test', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'equipment_id': "",
    'calibration_status': False,
    'test_parameters': {},
    'validation_report': ""
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
