from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class HeadgearState(TypedDict):
    material_specs: dict
    compliance_certs: List[str]
    safety_rating: float
    status: str

def validate_compliance(state: HeadgearState) -> HeadgearState:
    if 'ASTM' not in state['compliance_certs']:
        state['status'] = 'REJECTED_COMPLIANCE'
    return state

def inspect_spec(state: HeadgearState) -> HeadgearState:
    if state['safety_rating'] < 8.0:
        state['status'] = 'FAILED_SAFETY_THRESHOLD'
    else:
        state['status'] = 'PASSED_QA'
    return state

graph = StateGraph(HeadgearState)
graph.add_node('validate', validate_compliance)
graph.add_node('inspect', inspect_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_specs': {},
    'compliance_certs': [],
    'safety_rating': 0.0,
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
