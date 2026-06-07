from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmaState(TypedDict):
    batch_id: str
    compliance_docs: list
    validation_passed: bool

def validate_batch(state: PharmaState):
    # Simulate regulatory compliance check for drug batch
    is_valid = len(state['compliance_docs']) >= 3
    return {'validation_passed': is_valid}

def process_shipment(state: PharmaState):
    # Specialized pharmaceutical logistics workflow
    print(f'Processing batch {state['batch_id']} for distribution.')
    return state

graph = StateGraph(PharmaState)
graph.add_node('validate', validate_batch)
graph.add_node('ship', process_shipment)
graph.set_entry_point('validate')
graph.add_edge('validate', 'ship')
graph.add_edge('ship', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'compliance_docs': [],
    'validation_passed': False
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
