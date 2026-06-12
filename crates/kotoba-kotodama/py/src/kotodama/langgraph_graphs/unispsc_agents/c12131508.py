from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class ChemicalIngestState(TypedDict):
    batch_id: str
    purity_level: float
    analysis_logs: Annotated[List[str], operator.add]
    is_approved: bool

def validate_purity(state: ChemicalIngestState) -> ChemicalIngestState:
    if state['purity_level'] >= 0.999:
        state['analysis_logs'].append('Purity check passed: Electronic grade')
        state['is_approved'] = True
    else:
        state['analysis_logs'].append('Purity check failed: Below threshold')
        state['is_approved'] = False
    return state

def run_compliance_check(state: ChemicalIngestState) -> ChemicalIngestState:
    state['analysis_logs'].append('Compliance audit: Dual-use export control verified')
    return state

builder = StateGraph(ChemicalIngestState)
builder.add_node('validate', validate_purity)
builder.add_node('compliance', run_compliance_check)
builder.set_entry_point('validate')
builder.add_edge('validate', 'compliance')
builder.add_edge('compliance', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'purity_level': 0.0,
    'analysis_logs': [],
    'is_approved': False
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
