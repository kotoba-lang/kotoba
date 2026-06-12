from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    quality_docs: dict
    approved: bool

def validate_gmp(state: ProcurementState):
    state['approved'] = state['quality_docs'].get('gmp_verified', False)
    return state

def check_temp_logs(state: ProcurementState):
    # Simulate temperature validation logic
    temp_stable = state['quality_docs'].get('temp_log_status') == 'pass'
    state['approved'] = state['approved'] and temp_stable
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate_gmp', validate_gmp)
graph.add_node('check_temp_logs', check_temp_logs)
graph.set_entry_point('validate_gmp')
graph.add_edge('validate_gmp', 'check_temp_logs')
graph.add_edge('check_temp_logs', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'quality_docs': {},
    'approved': False
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
