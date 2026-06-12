from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class NadololState(TypedDict):
    batch_id: str
    purity_level: float
    has_coa: bool
    compliant: bool

def validate_quality(state: NadololState) -> NadololState:
    state['compliant'] = state['purity_level'] >= 99.0 and state['has_coa']
    return state

def check_stability(state: NadololState) -> NadololState:
    if state['compliant']:
        print(f'Batch {state['batch_id']} cleared for clinical distribution.')
    return state

graph = StateGraph(NadololState)
graph.add_node('validate', validate_quality)
graph.add_node('stability', check_stability)
graph.set_entry_point('validate')
graph.add_edge('validate', 'stability')
graph.add_edge('stability', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'purity_level': 0.0,
    'has_coa': False,
    'compliant': False
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
