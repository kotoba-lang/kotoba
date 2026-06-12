from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    material_specs: dict
    inspection_report: dict
    validation_status: bool

def validate_metallurgy(state: CastingState):
    # Simulate chemical composition validation for steel grade
    grade = state['material_specs'].get('grade')
    is_valid = grade in ['S25C', 'S45C', 'SCW480']
    return {'validation_status': is_valid}

def check_dimensions(state: CastingState):
    # Simulate dimensional tolerance verification
    return {'validation_status': state['validation_status'] and True}

builder = StateGraph(CastingState)
builder.add_node('metallurgy_check', validate_metallurgy)
builder.add_node('dimension_check', check_dimensions)
builder.add_edge('metallurgy_check', 'dimension_check')
builder.add_edge('dimension_check', END)
builder.set_entry_point('metallurgy_check')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_specs': {},
    'inspection_report': {},
    'validation_status': False
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
