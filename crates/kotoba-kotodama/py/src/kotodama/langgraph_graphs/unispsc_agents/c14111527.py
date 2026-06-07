from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PaperProductState(TypedDict):
    product_id: str
    spec_requirements: dict
    validation_results: List[str]
    is_compliant: bool

def validate_absorbency(state: PaperProductState) -> PaperProductState:
    req = state.get('spec_requirements', {})
    if req.get('absorbency_rate_g_per_m2', 0) >= 300:
        state['validation_results'].append('Absorbency check passed')
    else:
        state['validation_results'].append('Absorbency check failed')
    return state

def compliance_check(state: PaperProductState) -> str:
    if 'Absorbency check failed' in state['validation_results']:
        return 'fail'
    return 'pass'

graph = StateGraph(PaperProductState)
graph.add_node('validate', validate_absorbency)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_id': "",
    'spec_requirements': {},
    'validation_results': [],
    'is_compliant': False
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
