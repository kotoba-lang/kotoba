from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MetalPowderState(TypedDict):
    powder_id: str
    purity_level: float
    particle_distribution: float
    inspection_status: str
    safety_clearance: bool

def validate_purity(state: MetalPowderState):
    is_pure = state['purity_level'] >= 99.9
    return {'inspection_status': 'PASSED' if is_pure else 'FAILED'}

def check_safety(state: MetalPowderState):
    return {'safety_clearance': state['inspection_status'] == 'PASSED'}

graph = StateGraph(MetalPowderState)
graph.add_node('validate', validate_purity)
graph.add_node('safety', check_safety)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'powder_id': "",
    'purity_level': 0.0,
    'particle_distribution': 0.0,
    'inspection_status': "",
    'safety_clearance': False
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
