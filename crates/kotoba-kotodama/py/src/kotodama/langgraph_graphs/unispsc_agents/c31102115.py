from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    spec_data: dict
    validation_report: List[str]
    is_approved: bool

def validate_lead_content(state: CastingState):
    content = state['spec_data'].get('lead_purity', 0)
    if content < 95.0:
        state['validation_report'].append('Purity below standard')
    return state

def check_dimensions(state: CastingState):
    if 'tolerance' not in state['spec_data']:
        state['validation_report'].append('Missing tolerance data')
    return state

graph = StateGraph(CastingState)
graph.add_node('validate_purity', validate_lead_content)
graph.add_node('check_dims', check_dimensions)
graph.add_edge('validate_purity', 'check_dims')
graph.add_edge('check_dims', END)
graph.set_entry_point('validate_purity')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_report': [],
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
