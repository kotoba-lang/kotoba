from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ToxicologyState(TypedDict):
    test_kit_id: str
    batch_number: str
    compliance_docs: List[str]
    validation_status: str

def validate_compliance(state: ToxicologyState):
    if all(doc in state['compliance_docs'] for doc in ['SDS', 'CoA']):
        return {'validation_status': 'CLEARED'}
    return {'validation_status': 'PENDING_REVIEW'}

def perform_logistics_check(state: ToxicologyState):
    print(f'Checking storage requirements for batch {state['batch_number']}')
    return {'validation_status': 'READY_FOR_SHIPMENT'}

graph = StateGraph(ToxicologyState)
graph.add_node('compliance', validate_compliance)
graph.add_node('logistics', perform_logistics_check)
graph.add_edge('compliance', 'logistics')
graph.add_edge('logistics', END)
graph.set_entry_point('compliance')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'test_kit_id': "",
    'batch_number': "",
    'compliance_docs': [],
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
