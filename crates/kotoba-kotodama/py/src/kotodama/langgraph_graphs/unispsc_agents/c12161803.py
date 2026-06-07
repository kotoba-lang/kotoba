from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MetalPowderState(TypedDict):
    powder_id: str
    purity: float
    particle_size: float
    is_approved: bool
    logs: List[str]

def validate_powder(state: MetalPowderState) -> MetalPowderState:
    if state['purity'] >= 99.9 and state['particle_size'] < 50.0:
        state['is_approved'] = True
        state['logs'].append('Validation successful: High purity and fine size.')
    else:
        state['is_approved'] = False
        state['logs'].append('Validation failed: Purity or size out of specs.')
    return state

def route_by_validation(state: MetalPowderState) -> str:
    return 'approved' if state['is_approved'] else 'rejected'

graph = StateGraph(MetalPowderState)
graph.add_node('validate', validate_powder)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'powder_id': "",
    'purity': 0.0,
    'particle_size': 0.0,
    'is_approved': False,
    'logs': []
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
