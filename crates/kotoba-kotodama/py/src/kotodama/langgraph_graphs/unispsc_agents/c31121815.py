from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class CastingState(TypedDict):
    spec_data: dict
    validation_errors: List[str]
    is_approved: bool

def validate_material(state: CastingState):
    # Ensure lead-ceramic composition meets hazardous material safety protocols
    comp = state['spec_data'].get('composition', {})
    if 'lead' not in comp:
        state['validation_errors'].append('Lead content certification missing.')
    return {'validation_errors': state['validation_errors']}

def check_dimensions(state: CastingState):
    # Verify dimensional tolerance for high-precision casting
    if state['spec_data'].get('tolerance', 0) > 0.05:
        state['validation_errors'].append('Tolerance exceeds precision casting limits.')
    return {'validation_errors': state['validation_errors']}

workflow = StateGraph(CastingState)
workflow.add_node('material_check', validate_material)
workflow.add_node('dim_check', check_dimensions)
workflow.set_entry_point('material_check')
workflow.add_edge('material_check', 'dim_check')
workflow.add_edge('dim_check', END)
graph = workflow.compile()

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
