from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class DiagnosticState(TypedDict):
    commodity_id: str
    batch_id: str
    quality_checks: List[str]
    is_cleared: bool

def validate_cold_chain(state: DiagnosticState) -> DiagnosticState:
    state['quality_checks'].append('Cold chain verification passed')
    return state

def run_compliance_check(state: DiagnosticState) -> DiagnosticState:
    state['is_cleared'] = True
    return state

graph = StateGraph(DiagnosticState)
graph.add_node('cold_chain', validate_cold_chain)
graph.add_node('compliance', run_compliance_check)
graph.add_edge('cold_chain', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('cold_chain')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_id': "",
    'batch_id': "",
    'quality_checks': [],
    'is_cleared': False
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
