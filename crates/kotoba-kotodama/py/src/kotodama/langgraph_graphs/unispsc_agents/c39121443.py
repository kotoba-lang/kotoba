from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ConnectorState(TypedDict):
    spec_data: dict
    validation_errors: List[str]
    is_approved: bool

def validate_insulation(state: ConnectorState):
    voltage = state['spec_data'].get('voltage', 0)
    if voltage < 10: state['validation_errors'].append('Voltage rating too low for underground grade')
    return state

def check_ip_rating(state: ConnectorState):
    if state['spec_data'].get('ip_rating', 0) < 68: state['validation_errors'].append('Insufficient waterproof rating')
    return state

graph = StateGraph(ConnectorState)
graph.add_node('validate_insulation', validate_insulation)
graph.add_node('check_ip', check_ip_rating)
graph.set_entry_point('validate_insulation')
graph.add_edge('validate_insulation', 'check_ip')
graph.add_edge('check_ip', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_errors': [],
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
