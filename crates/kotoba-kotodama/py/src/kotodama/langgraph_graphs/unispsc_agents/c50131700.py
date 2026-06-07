from typing import TypedDict
from langgraph.graph import StateGraph, END

class DairyState(TypedDict):
    temp_log: list[float]
    is_safe: bool
    compliance_docs: list[str]

def validate_cold_chain(state: DairyState):
    if all(temp <= 4.0 for temp in state['temp_log']):
        return {'is_safe': True}
    return {'is_safe': False}

def check_certification(state: DairyState):
    return {'is_safe': 'HACCP' in state['compliance_docs']}

graph = StateGraph(DairyState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('check_certification', check_certification)
graph.set_entry_point('validate_cold_chain')
graph.add_edge('validate_cold_chain', 'check_certification')
graph.add_edge('check_certification', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'temp_log': [],
    'is_safe': False,
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
