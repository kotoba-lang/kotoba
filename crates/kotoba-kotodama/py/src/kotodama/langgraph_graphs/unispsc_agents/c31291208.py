from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class MagnesiumState(TypedDict):
    spec_sheet: dict
    validation_errors: List[str]
    is_approved: bool

def validate_alloy_grade(state: MagnesiumState):
    grade = state['spec_sheet'].get('grade')
    if grade not in ['AZ31B', 'ZK60A']:
        state['validation_errors'].append('Unsupported magnesium alloy grade')
    return state

def check_surface_finish(state: MagnesiumState):
    if not state.get('spec_sheet', {}).get('anodization_certified', False):
        state['validation_errors'].append('Missing mandatory corrosion protection certification')
    return state

builder = StateGraph(MagnesiumState)
builder.add_node('validate_grade', validate_alloy_grade)
builder.add_node('check_finish', check_surface_finish)
builder.add_edge('validate_grade', 'check_finish')
builder.add_edge('check_finish', END)
builder.set_entry_point('validate_grade')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_sheet': {},
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
