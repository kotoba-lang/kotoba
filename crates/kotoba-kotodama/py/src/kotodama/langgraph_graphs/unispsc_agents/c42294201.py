from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class SurgicalKitState(TypedDict):
    kit_id: str
    inspection_passed: bool
    certifications: List[str]
    validation_complete: bool

def validate_materials(state: SurgicalKitState):
    # Simulate material compliance check for surgical grade steel
    state['inspection_passed'] = True
    print(f'Validating materials for kit: {state['kit_id']}')
    return state

def verify_regulatory_docs(state: SurgicalKitState):
    # Verify ISO 13485 and device registration
    state['validation_complete'] = 'ISO-13485' in state['certifications']
    return state

graph = StateGraph(SurgicalKitState)
graph.add_node('validate', validate_materials)
graph.add_node('verify', verify_regulatory_docs)
graph.set_entry_point('validate')
graph.add_edge('validate', 'verify')
graph.add_edge('verify', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'kit_id': "",
    'inspection_passed': False,
    'certifications': [],
    'validation_complete': False
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
