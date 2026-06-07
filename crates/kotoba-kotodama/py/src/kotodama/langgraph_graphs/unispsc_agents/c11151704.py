from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    purity: float
    particle_size: float
    is_stable: bool
    validation_log: List[str]

def validate_catalyst_purity(state: CatalystState):
    log = state.get('validation_log', [])
    if state['purity'] >= 0.99:
        log.append('Purity check passed')
    else:
        log.append('Purity check failed')
    return {'validation_log': log}

def check_stability(state: CatalystState):
    log = state.get('validation_log', [])
    if state['is_stable']:
        log.append('Stability validated')
    else:
        log.append('Stability unstable')
    return {'validation_log': log}

graph = StateGraph(CatalystState)
graph.add_node('validate_purity', validate_catalyst_purity)
graph.add_node('check_stability', check_stability)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_stability')
graph.add_edge('check_stability', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'particle_size': 0.0,
    'is_stable': False,
    'validation_log': []
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
