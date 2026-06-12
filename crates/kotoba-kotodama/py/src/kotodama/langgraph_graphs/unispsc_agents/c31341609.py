from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    specs: dict
    validated: bool
    error: str

def validate_materials(state: AssemblyState):
    grade = state['specs'].get('material_grade')
    state['validated'] = grade in ['304', '316', '316L']
    return state

def check_dimensions(state: AssemblyState):
    if state['validated']:
        tolerance = state['specs'].get('tolerance', 0.0)
        state['validated'] = tolerance <= 0.05
    return state

builder = StateGraph(AssemblyState)
builder.add_node('validate_materials', validate_materials)
builder.add_node('check_dimensions', check_dimensions)
builder.set_entry_point('validate_materials')
builder.add_edge('validate_materials', 'check_dimensions')
builder.add_edge('check_dimensions', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'validated': False,
    'error': ""
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
