from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RareEarthState(TypedDict):
    material_code: str
    purity_level: float
    compliance_checks: List[str]
    validation_status: str

def validate_material_purity(state: RareEarthState) -> RareEarthState:
    if state['purity_level'] >= 99.9:
        state['validation_status'] = 'CERTIFIED_HIGH_GRADE'
    else:
        state['validation_status'] = 'REJECTED_LOW_GRADE'
    return state

def run_compliance_audit(state: RareEarthState) -> RareEarthState:
    state['compliance_checks'].append('EXPORT_CONTROL_VERIFIED')
    return state

builder = StateGraph(RareEarthState)
builder.add_node('validate', validate_material_purity)
builder.add_node('compliance', run_compliance_audit)
builder.add_edge('validate', 'compliance')
builder.add_edge('compliance', END)
builder.set_entry_point('validate')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_code': "",
    'purity_level': 0.0,
    'compliance_checks': [],
    'validation_status': ""
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
