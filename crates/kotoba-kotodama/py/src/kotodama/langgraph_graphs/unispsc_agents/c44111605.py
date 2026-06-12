from typing import TypedDict
from langgraph.graph import StateGraph, END

class CashBoxState(TypedDict):
    box_id: str
    lock_type: str
    is_secure: bool
    validation_log: list

def validate_lock(state: CashBoxState) -> CashBoxState:
    secure_types = ['keyed', 'electronic', 'biometric']
    state['is_secure'] = state['lock_type'] in secure_types
    state['validation_log'] = ['Lock check performed']
    return state

def compliance_check(state: CashBoxState) -> CashBoxState:
    if not state.get('is_secure'):
        state['validation_log'].append('Security risk: non-standard lock')
    return state

graph = StateGraph(CashBoxState)
graph.add_node('validate_lock', validate_lock)
graph.add_node('compliance_check', compliance_check)
graph.set_entry_point('validate_lock')
graph.add_edge('validate_lock', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'box_id': "",
    'lock_type': "",
    'is_secure': False,
    'validation_log': []
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
