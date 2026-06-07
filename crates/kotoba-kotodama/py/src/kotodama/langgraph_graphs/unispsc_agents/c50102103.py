from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class NectarineState(TypedDict):
    inspection_data: dict
    approved: bool
    qc_passed: bool

def validate_quality(state: NectarineState) -> NectarineState:
    brix = state['inspection_data'].get('brix', 0)
    state['qc_passed'] = brix >= 12.0
    return state

def check_compliance(state: NectarineState) -> NectarineState:
    state['approved'] = state['qc_passed'] and 'pesticide_cert' in state['inspection_data']
    return state

graph = StateGraph(NectarineState)
graph.add_node('qc_check', validate_quality)
graph.add_node('compliance_check', check_compliance)
graph.set_entry_point('qc_check')
graph.add_edge('qc_check', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'inspection_data': {},
    'approved': False,
    'qc_passed': False
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
