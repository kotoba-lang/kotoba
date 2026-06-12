from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_id: str
    quality_docs: list
    is_compliant: bool

def validate_pharma_docs(state: ProcurementState):
    # Perform specific checks for pharmaceutical certifications
    state['is_compliant'] = 'CoA' in state['quality_docs'] and 'GMP' in state['quality_docs']
    return state

def check_storage_requirements(state: ProcurementState):
    # Simulate logistics validation
    print(f'Validating specialized storage for {state['product_id']}')
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate_docs', validate_pharma_docs)
graph.add_node('check_storage', check_storage_requirements)
graph.add_edge('validate_docs', 'check_storage')
graph.add_edge('check_storage', END)
graph.set_entry_point('validate_docs')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_id': "",
    'quality_docs': [],
    'is_compliant': False
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
