from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CobaltState(TypedDict):
    purity: float
    origin: str
    is_compliant: bool
    log: Annotated[Sequence[str], operator.add]

def validate_purity(state: CobaltState) -> CobaltState:
    if state['purity'] < 99.5:
        return {'is_compliant': False, 'log': ['Purity check failed: below threshold']}
    return {'is_compliant': True, 'log': ['Purity check passed']}

def verify_origin(state: CobaltState) -> CobaltState:
    if not state['origin']:
        return {'is_compliant': False, 'log': ['Origin missing']}
    return {'is_compliant': True, 'log': ['Origin verified']}

def router(state: CobaltState) -> str:
    if not state.get('is_compliant', True):
        return 'END'
    return 'next_step'

graph = StateGraph(CobaltState)
graph.add_node('validate', validate_purity)
graph.add_node('verify', verify_origin)
graph.set_entry_point('validate')
graph.add_edge('validate', 'verify')
graph.add_edge('verify', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'origin': "",
    'is_compliant': False,
    'log': []
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
