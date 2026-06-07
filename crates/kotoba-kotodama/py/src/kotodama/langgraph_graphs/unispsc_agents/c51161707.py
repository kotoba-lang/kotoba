from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    api_name: str
    purity_level: float
    compliance_docs: list

def validate_api_spec(state: ProcurementState):
    assert state['purity_level'] >= 99.0, 'Purity below pharmaceutical Grade'
    return {'compliance_docs': ['GMP_CERT', 'COA']}

def check_hazmat(state: ProcurementState):
    print('Checking dangerous goods protocols for Bamifylline')
    return {'status': 'validated'}

graph = StateGraph(ProcurementState)
graph.add_node('validation', validate_api_spec)
graph.add_node('hazmat_check', check_hazmat)
graph.set_entry_point('validation')
graph.add_edge('validation', 'hazmat_check')
graph.add_edge('hazmat_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'api_name': "",
    'purity_level': 0.0,
    'compliance_docs': []
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
