from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    specification: dict
    validation_result: bool
    error_log: list

def validate_iso_compliance(state: State):
    is_compliant = state['specification'].get('iso_11140_cert') is True
    return {'validation_result': is_compliant, 'error_log': [] if is_compliant else ['Missing ISO certification']}

def check_shelf_life(state: State):
    if not state.get('validation_result'): return state
    valid = state['specification'].get('days_to_expiry', 0) > 90
    return {'validation_result': valid, 'error_log': [] if valid else ['Insufficient shelf life']}

graph = StateGraph(State)
graph.add_node('iso_check', validate_iso_compliance)
graph.add_node('expiry_check', check_shelf_life)
graph.add_edge('iso_check', 'expiry_check')
graph.add_edge('expiry_check', END)
graph.set_entry_point('iso_check')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specification': {},
    'validation_result': False,
    'error_log': []
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
