from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity_code: str
    spec_data: dict
    validation_passed: bool
    errors: List[str]

def validate_gmp_compliance(state: ProcurementState) -> ProcurementState:
    if 'GMP_certificate_version' not in state['spec_data']:
        state['errors'].append('Missing GMP certification')
        state['validation_passed'] = False
    return state

def check_purity_threshold(state: ProcurementState) -> ProcurementState:
    if state.get('validation_passed', True):
        purity = state['spec_data'].get('batch_purity_percentage', 0)
        if purity < 99.0:
            state['errors'].append('Purity below 99.0% threshold')
            state['validation_passed'] = False
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate_gmp', validate_gmp_compliance)
graph.add_node('check_purity', check_purity_threshold)
graph.add_edge('validate_gmp', 'check_purity')
graph.add_edge('check_purity', END)
graph.set_entry_point('validate_gmp')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'spec_data': {},
    'validation_passed': False,
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
