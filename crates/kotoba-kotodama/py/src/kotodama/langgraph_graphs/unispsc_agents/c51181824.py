from typing import TypedDict
from langgraph.graph import StateGraph, END
class PharmaProcurementState(TypedDict):
    purity_level: float
    gmp_status: bool
    compliance_docs: list
    is_approved: bool
def validate_quality(state: PharmaProcurementState):
    if state['purity_level'] >= 99.0 and state['gmp_status']:
        return {'is_approved': True}
    return {'is_approved': False}
def verify_compliance(state: PharmaProcurementState):
    required = ['SDS', 'CoA', 'GMP_Cert']
    all_docs = all(doc in state['compliance_docs'] for doc in required)
    return {'is_approved': all_docs}
builder = StateGraph(PharmaProcurementState)
builder.add_node('quality_check', validate_quality)
builder.add_node('compliance_check', verify_compliance)
builder.set_entry_point('quality_check')
builder.add_edge('quality_check', 'compliance_check')
builder.add_edge('compliance_check', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'gmp_status': False,
    'compliance_docs': [],
    'is_approved': False
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
