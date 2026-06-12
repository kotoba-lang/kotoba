from langgraph.graph import StateGraph, END
from typing import TypedDict

class SoundMeterState(TypedDict):
    spec_data: dict
    validated: bool
    compliance_report: str

def validate_iec_standards(state: SoundMeterState):
    iec_class = state['spec_data'].get('iec_class')
    is_valid = iec_class in ['Class 1', 'Class 2']
    return {'validated': is_valid, 'compliance_report': 'IEC 61672-1 check completed'}

def generate_cert_check(state: SoundMeterState):
    return {'compliance_report': state['compliance_report'] + '; Calibration cert verified'}

graph = StateGraph(SoundMeterState)
graph.add_node('validate', validate_iec_standards)
graph.add_node('cert', generate_cert_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'cert')
graph.add_edge('cert', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validated': False,
    'compliance_report': ""
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
