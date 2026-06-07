from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    purity: float
    cas_number: str
    compliance_docs: List[str]
    status: str

def validate_coa(state: ChemicalState):
    if state['purity'] >= 99.0:
        return {'status': 'validated'}
    return {'status': 'rejected'}

def check_sds(state: ChemicalState):
    if 'SDS_available' in state['compliance_docs']:
        return {'status': 'ready'}
    return {'status': 'missing_docs'}

graph = StateGraph(ChemicalState)
graph.add_node('validate_coa', validate_coa)
graph.add_node('check_sds', check_sds)
graph.set_entry_point('validate_coa')
graph.add_edge('validate_coa', 'check_sds')
graph.add_edge('check_sds', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'cas_number': "",
    'compliance_docs': [],
    'status': ""
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
