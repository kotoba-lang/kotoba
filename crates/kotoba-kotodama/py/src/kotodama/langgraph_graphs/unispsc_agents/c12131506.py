from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MetalOxideState(TypedDict):
    commodity_code: str
    purity: float
    inspection_passed: bool
    compliance_tags: List[str]

def validate_purity(state: MetalOxideState):
    passed = state['purity'] >= 99.9
    return {'inspection_passed': passed}

def route_compliance(state: MetalOxideState):
    if not state['inspection_passed']:
        return 'flag_for_review'
    return 'process_order'

def flag_for_review(state: MetalOxideState):
    return {'compliance_tags': ['MANUAL_REVIEW_REQUIRED']}

def process_order(state: MetalOxideState):
    return {'compliance_tags': ['READY_FOR_LOGISTICS']}

graph = StateGraph(MetalOxideState)
graph.add_node('validate', validate_purity)
graph.add_node('flag_for_review', flag_for_review)
graph.add_node('process_order', process_order)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_compliance)
graph.add_edge('flag_for_review', END)
graph.add_edge('process_order', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'purity': 0.0,
    'inspection_passed': False,
    'compliance_tags': []
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
