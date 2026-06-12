from typing import TypedDict
from langgraph.graph import StateGraph, END

class SmokeDetectorState(TypedDict):
    model_id: str
    compliance_certs: list
    sensitivity_test_result: float
    status: str

def validate_certification(state: SmokeDetectorState):
    required = ['UL217', 'EN14604']
    valid = all(cert in state['compliance_certs'] for cert in required)
    return {'status': 'CERTIFIED' if valid else 'FAILED_CERTIFICATION'}

def process_sensitivity(state: SmokeDetectorState):
    if state['sensitivity_test_result'] < 0.05:
        return {'status': 'PASSED_CALIBRATION'}
    return {'status': 'FAILED_CALIBRATION'}

graph = StateGraph(SmokeDetectorState)
graph.add_node('validate_cert', validate_certification)
graph.add_node('test_sensor', process_sensitivity)
graph.set_entry_point('validate_cert')
graph.add_edge('validate_cert', 'test_sensor')
graph.add_edge('test_sensor', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'model_id': "",
    'compliance_certs': [],
    'sensitivity_test_result': 0.0,
    'status': ""
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
