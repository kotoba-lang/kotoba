from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ApricotProcurementState(TypedDict):
    origin: str
    quality_score: float
    phytosanitary_certs: List[str]
    is_approved: bool

def validate_freshness(state: ApricotProcurementState):
    # Simulate quality inspection logic for perishables
    state['is_approved'] = state['quality_score'] >= 0.8 and len(state['phytosanitary_certs']) > 0
    return state

def route_procurement(state: ApricotProcurementState):
    return 'approve' if state['is_approved'] else 'reject'

graph = StateGraph(ApricotProcurementState)
graph.add_node('inspector', validate_freshness)
graph.set_entry_point('inspector')
graph.add_edge('inspector', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'origin': "",
    'quality_score': 0.0,
    'phytosanitary_certs': [],
    'is_approved': False
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
