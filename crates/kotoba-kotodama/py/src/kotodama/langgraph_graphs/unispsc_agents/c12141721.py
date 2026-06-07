from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class EnzymeState(TypedDict):
    commodity_code: str
    quality_metrics: dict
    workflow_steps: List[str]
    validation_status: bool

def validate_purity(state: EnzymeState) -> EnzymeState:
    purity = state['quality_metrics'].get('purity', 0)
    state['validation_status'] = purity >= 99.0
    state['workflow_steps'].append('purity_checked')
    return state

def cold_chain_verification(state: EnzymeState) -> EnzymeState:
    temp = state['quality_metrics'].get('storage_temp', 25)
    if temp <= 4.0:
        state['workflow_steps'].append('cold_chain_verified')
    return state

graph = StateGraph(EnzymeState)
graph.add_node('validate', validate_purity)
graph.add_node('cold_chain', cold_chain_verification)
graph.set_entry_point('validate')
graph.add_edge('validate', 'cold_chain')
graph.add_edge('cold_chain', END)

# The graph instance is ready for compilation
# compiled_graph = graph.compile()

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'quality_metrics': {},
    'workflow_steps': [],
    'validation_status': False
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
