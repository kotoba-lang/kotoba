from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ScintigraphyState(TypedDict):
    device_id: str
    calibration_compliant: bool
    validation_logs: List[str]

def validate_radiation_safety(state: ScintigraphyState):
    state['validation_logs'].append('Verifying radiation shielding compliance...')
    return {'calibration_compliant': True}

def check_dicom_protocols(state: ScintigraphyState):
    state['validation_logs'].append('Checking DICOM image transmission protocols...')
    return state

graph = StateGraph(ScintigraphyState)
graph.add_node('safety_check', validate_radiation_safety)
graph.add_node('dicom_validation', check_dicom_protocols)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'dicom_validation')
graph.add_edge('dicom_validation', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'device_id': "",
    'calibration_compliant': False,
    'validation_logs': []
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
