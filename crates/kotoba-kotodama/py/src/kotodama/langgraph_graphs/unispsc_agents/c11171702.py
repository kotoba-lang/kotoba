from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MetalOxideState(TypedDict):
    purity_level: float
    particle_size: float
    validation_logs: Annotated[Sequence[str], operator.add]

def validate_purity(state: MetalOxideState):
    log = 'Purity validated' if state['purity_level'] >= 99.5 else 'Purity failed'
    return {'validation_logs': [log]}

def check_particle_size(state: MetalOxideState):
    log = 'Size within range' if 1.0 <= state['particle_size'] <= 50.0 else 'Size out of spec'
    return {'validation_logs': [log]}

graph = StateGraph(MetalOxideState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_particle_size', check_particle_size)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_particle_size')
graph.add_edge('check_particle_size', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'particle_size': 0.0,
    'validation_logs': []
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
