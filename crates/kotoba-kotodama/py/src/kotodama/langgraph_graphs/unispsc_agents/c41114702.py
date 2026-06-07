from langgraph.graph import StateGraph, END
from typing import TypedDict
class TesterState(TypedDict):
    spec_data: dict
    validation_status: str
    compliance_score: float
def validate_specs(state: TesterState):
    # Perform ISO/AATCC compliance check logic here
    if state['spec_data'].get('standard') in ['ISO', 'AATCC']:
        return {'validation_status': 'COMPLIANT', 'compliance_score': 1.0}
    return {'validation_status': 'FAILED', 'compliance_score': 0.0}
def check_calibration(state: TesterState):
    # Logic to verify calibration certificate upload
    return {'validation_status': 'CERTIFIED' if state['spec_data'].get('cal_cert') else 'PENDING'}
graph = StateGraph(TesterState)
graph.add_node('validate', validate_specs)
graph.add_node('calibrate', check_calibration)
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_status': "",
    'compliance_score': 0.0
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
