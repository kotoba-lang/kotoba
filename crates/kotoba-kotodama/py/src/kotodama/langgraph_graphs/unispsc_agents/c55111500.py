from typing import TypedDict
from langgraph.graph import StateGraph, END

class ContentState(TypedDict):
    license_type: str
    file_format: str
    is_compliant: bool

def validate_format(state: ContentState) -> ContentState:
    supported = ['pdf', 'epub', 'mp3', 'aac']
    state['is_compliant'] = state['file_format'].lower() in supported
    return state

def check_licensing(state: ContentState) -> ContentState:
    if state['license_type'] not in ['perpetual', 'subscription']:
        state['is_compliant'] = False
    return state

graph = StateGraph(ContentState)
graph.add_node('validate_format', validate_format)
graph.add_node('check_licensing', check_licensing)
graph.set_entry_point('validate_format')
graph.add_edge('validate_format', 'check_licensing')
graph.add_edge('check_licensing', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'license_type': "",
    'file_format': "",
    'is_compliant': False
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
