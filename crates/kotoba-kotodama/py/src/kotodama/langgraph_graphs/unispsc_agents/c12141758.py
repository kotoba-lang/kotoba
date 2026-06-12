from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SolventState(TypedDict):
    purity_level: float
    contaminants: List[str]
    validation_status: str

def check_purity(state: SolventState):
    if state['purity_level'] >= 99.999:
        return {'validation_status': 'PASS'}
    return {'validation_status': 'FAIL'}

def audit_contaminants(state: SolventState):
    if not state['contaminants']:
        return {'validation_status': 'AUDIT_CLEAN'}
    return {'validation_status': 'AUDIT_FAILED'}

graph = StateGraph(SolventState)
graph.add_node('check_purity', check_purity)
graph.add_node('audit_contaminants', audit_contaminants)
graph.set_entry_point('check_purity')
graph.add_edge('check_purity', 'audit_contaminants')
graph.add_edge('audit_contaminants', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'contaminants': [],
    'validation_status': ""
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
