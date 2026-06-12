from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SoundMeterState(TypedDict):
    model_number: str
    calibration_date: str
    compliance_std: str
    is_validated: bool

def validate_calibration(state: SoundMeterState):
    # Business logic for calibration compliance check
    status = 'CAL-OK' in state.get('calibration_date', '')
    return {'is_validated': status}

def hardware_inspection(state: SoundMeterState):
    # Placeholder for logic verifying specs against NIST standards
    return {'is_validated': True if state['compliance_std'] == 'IEC 61672-1' else False}

graph = StateGraph(SoundMeterState)
graph.add_node('validate_cal', validate_calibration)
graph.add_node('hardware_check', hardware_inspection)
graph.add_edge('validate_cal', 'hardware_check')
graph.add_edge('hardware_check', END)
graph.set_entry_point('validate_cal')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'model_number': "",
    'calibration_date': "",
    'compliance_std': "",
    'is_validated': False
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
