from langgraph.graph import StateGraph, END
from typing import TypedDict

class BioState(TypedDict):
    material_name: str
    purity_level: float
    storage_temp: str
    is_sterile: bool

def validate_purity(state: BioState):
    if state['purity_level'] < 0.99:
        raise ValueError('Purity below 99% for S. pombe media additive')
    return 'VALIDATED'

def check_cold_chain(state: BioState):
    if state['storage_temp'] not in ['-20C', '4C']:
        return 'FLAG_TEMP_RISK'
    return 'READY'

graph = StateGraph(BioState)
graph.add_node('purity_check', validate_purity)
graph.add_node('cold_chain', check_cold_chain)
graph.set_entry_point('purity_check')
graph.add_edge('purity_check', 'cold_chain')
graph.add_edge('cold_chain', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_name': "",
    'purity_level': 0.0,
    'storage_temp': "",
    'is_sterile': False
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
