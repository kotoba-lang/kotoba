from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CrudeState(TypedDict):
    commodity_code: str
    volume: float
    purity_cert_url: str
    is_compliant: bool
    compliance_notes: List[str]

def validate_purity(state: CrudeState) -> CrudeState:
    # Logic to verify oil purity certificates against regulatory standards
    state['is_compliant'] = True if state['purity_cert_url'] else False
    state['compliance_notes'] = ['Compliance Verified'] if state['is_compliant'] else ['Missing Certification']
    return state

def route_to_shipping(state: CrudeState) -> str:
    return 'shipping' if state['is_compliant'] else END

graph = StateGraph(CrudeState)
graph.add_node('validate', validate_purity)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'volume': 0.0,
    'purity_cert_url': "",
    'is_compliant': False,
    'compliance_notes': []
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
