from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ERPProcurementState(TypedDict):
    requirements: List[str]
    vendor_compliance: bool
    validation_checklist: List[str]

def validate_vendor(state: ERPProcurementState) -> ERPProcurementState:
    state['vendor_compliance'] = True
    state['validation_checklist'].append('Vendor verified against ISO27001')
    return state

def check_integration(state: ERPProcurementState) -> ERPProcurementState:
    state['validation_checklist'].append('API requirements verified')
    return state

graph = StateGraph(ERPProcurementState)
graph.add_node('validate_vendor', validate_vendor)
graph.add_node('check_integration', check_integration)
graph.add_edge('validate_vendor', 'check_integration')
graph.add_edge('check_integration', END)
graph.set_entry_point('validate_vendor')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'requirements': [],
    'vendor_compliance': False,
    'validation_checklist': []
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
