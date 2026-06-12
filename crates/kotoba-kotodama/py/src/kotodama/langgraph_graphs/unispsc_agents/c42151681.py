from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DentalSupplyState(TypedDict):
    item_name: str
    compliance_docs: List[str]
    is_sterile: bool
    approved: bool

def validate_compliance(state: DentalSupplyState):
    required = ['FDA_Approval', 'ISO_13485']
    state['approved'] = all(doc in state['compliance_docs'] for doc in required)
    return state

def check_sterility(state: DentalSupplyState):
    state['is_sterile'] = True
    return state

graph = StateGraph(DentalSupplyState)
graph.add_node('validate', validate_compliance)
graph.add_node('check_sterility', check_sterility)
graph.add_edge('validate', 'check_sterility')
graph.add_edge('check_sterility', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'item_name': "",
    'compliance_docs': [],
    'is_sterile': False,
    'approved': False
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
