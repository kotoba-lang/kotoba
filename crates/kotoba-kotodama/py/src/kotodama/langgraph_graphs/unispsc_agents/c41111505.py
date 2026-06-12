from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class AuditState(TypedDict):
    weight_set_id: str
    oiml_class: str
    calibration_status: bool
    errors: List[str]

def validate_oiml_compliance(state: AuditState):
    if state['oiml_class'] not in ['E1', 'E2', 'F1', 'F2', 'M1']:
        state['errors'].append('Invalid OIML class')
    return state

def check_calibration_certificate(state: AuditState):
    if not state['calibration_status']:
        state['errors'].append('Missing valid calibration certificate')
    return state

graph = StateGraph(AuditState)
graph.add_node('validate', validate_oiml_compliance)
graph.add_node('certify', check_calibration_certificate)
graph.set_entry_point('validate')
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'weight_set_id': "",
    'oiml_class': "",
    'calibration_status': False,
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
