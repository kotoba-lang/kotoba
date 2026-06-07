from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToyProcurementState(TypedDict):
    product_id: str
    compliance_docs: list[str]
    status: str

def validate_safety_certs(state: ToyProcurementState):
    # Simulate verification of EN71 or ASTM F963 compliance
    state['status'] = 'CERTIFIED' if 'ST_CERT' in state['compliance_docs'] else 'PENDING'
    return state

def check_toxicity(state: ToyProcurementState):
    # Simulate material toxicity validation
    if state.get('status') == 'CERTIFIED':
        state['status'] = 'APPROVED'
    return state

graph = StateGraph(ToyProcurementState)
graph.add_node('safety', validate_safety_certs)
graph.add_node('toxicity', check_toxicity)
graph.set_entry_point('safety')
graph.add_edge('safety', 'toxicity')
graph.add_edge('toxicity', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_id': "",
    'compliance_docs': [],
    'status': ""
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
