from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class CalligraphyState(TypedDict):
    spec_data: dict
    is_validated: bool

def validate_nib_specification(state: CalligraphyState):
    nib = state['spec_data'].get('nib_material', '')
    return {'is_validated': nib in ['metal', 'nylon', 'natural_hair']}

def quality_check(state: CalligraphyState):
    return {'is_validated': state['is_validated'] and state['spec_data'].get('ink_type') == 'archival'}

graph = StateGraph(CalligraphyState)
graph.add_node('validate_nib', validate_nib_specification)
graph.add_node('qc', quality_check)
graph.add_edge('validate_nib', 'qc')
graph.add_edge('qc', END)
graph.set_entry_point('validate_nib')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'is_validated': False
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
