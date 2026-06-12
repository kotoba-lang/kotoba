from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PaintWorkflowState(TypedDict):
    product_id: str
    safety_certs: List[str]
    washability_grade: int
    approved: bool

def validate_safety(state: PaintWorkflowState):
    # Validate against ASTM D-4236 standards
    state['approved'] = 'ASTM_D4236' in state['safety_certs']
    return state

def check_quality(state: PaintWorkflowState):
    # Fine-grained check of washability index
    if state.get('washability_grade', 0) > 8:
        state['approved'] = True
    return state

graph = StateGraph(PaintWorkflowState)
graph.add_node('safety_check', validate_safety)
graph.add_node('quality_check', check_quality)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'quality_check')
graph.add_edge('quality_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_id': "",
    'safety_certs': [],
    'washability_grade': 0,
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
