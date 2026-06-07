from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class CytologyState(TypedDict):
    product_specs: dict
    compliance_checks: List[str]
    validation_status: str

def validate_medical_compliance(state: CytologyState):
    checks = state['compliance_checks']
    if 'ISO13485' in state['product_specs'].get('certs', []):
        checks.append('Compliance Passed')
    else:
        checks.append('Compliance Failed')
    return {'compliance_checks': checks, 'validation_status': 'verified'}

def route_verification(state: CytologyState):
    if state['validation_status'] == 'verified':
        return 'END'
    return 'END'

graph = StateGraph(CytologyState)
graph.add_node('compliance', validate_medical_compliance)
graph.set_entry_point('compliance')
graph.add_edge('compliance', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_specs': {},
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
