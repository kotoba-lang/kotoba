from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class EnzymeState(TypedDict):
    purity: float
    activity_units: int
    coa_verified: bool
    passed_inspection: bool

def validate_purity(state: EnzymeState):
    state['passed_inspection'] = state['purity'] >= 99.0
    return state

def verify_coa(state: EnzymeState):
    return {'coa_verified': True} if state['activity_units'] > 2000 else {'coa_verified': False}

graph = StateGraph(EnzymeState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('verify_coa', verify_coa)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'verify_coa')
graph.add_edge('verify_coa', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'activity_units': 0,
    'coa_verified': False,
    'passed_inspection': False
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
