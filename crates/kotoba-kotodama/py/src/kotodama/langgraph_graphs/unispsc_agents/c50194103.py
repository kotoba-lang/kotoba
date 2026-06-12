from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LemonPureeState(TypedDict):
    batch_id: str
    brix: float
    ph: float
    is_compliant: bool
    history: List[str]

def quality_check(state: LemonPureeState):
    # Business logic for validation
    if 8.0 <= state['brix'] <= 12.0 and 2.0 <= state['ph'] <= 2.5:
        return {'is_compliant': True, 'history': state['history'] + ['QC Passed']}
    return {'is_compliant': False, 'history': state['history'] + ['QC Failed']}

def cold_chain_verification(state: LemonPureeState):
    # Logic for cold chain audit
    return {'history': state['history'] + ['Cold Chain Verified']}

graph = StateGraph(LemonPureeState)
graph.add_node('qc', quality_check)
graph.add_node('cold_chain', cold_chain_verification)
graph.set_entry_point('qc')
graph.add_edge('qc', 'cold_chain')
graph.add_edge('cold_chain', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'brix': 0.0,
    'ph': 0.0,
    'is_compliant': False,
    'history': []
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
