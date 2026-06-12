from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class EmbeddingState(TypedDict):
    spec_data: dict
    validation_errors: List[str]
    is_approved: bool

def validate_msds(state: EmbeddingState):
    if 'msds_compliance' not in state['spec_data']:
        state['validation_errors'].append('Missing SDS documentation')
    return state

def check_storage(state: EmbeddingState):
    temp = state['spec_data'].get('storage_temperature_range')
    if not temp: state['validation_errors'].append('Storage temp required')
    return state

graph = StateGraph(EmbeddingState)
graph.add_node('validate_msds', validate_msds)
graph.add_node('check_storage', check_storage)
graph.set_entry_point('validate_msds')
graph.add_edge('validate_msds', 'check_storage')
graph.add_edge('check_storage', END)
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
