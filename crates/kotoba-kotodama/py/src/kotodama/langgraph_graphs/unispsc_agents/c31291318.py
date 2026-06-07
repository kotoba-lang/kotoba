from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExtrusionState(TypedDict):
    part_specs: dict
    validation_results: list
    is_compliant: bool

def validate_geometry(state: ExtrusionState):
    # Simulated precision geometry check against CAD specs
    state['validation_results'].append('Geometry check passed')
    return {'validation_results': state['validation_results']}

def perform_material_analysis(state: ExtrusionState):
    # Simulated alloy composition verification
    state['validation_results'].append('Material grade verified')
    return {'validation_results': state['validation_results']}

def consolidate_results(state: ExtrusionState):
    state['is_compliant'] = all(res in state['validation_results'] for res in ['Geometry check passed', 'Material grade verified'])
    return {'is_compliant': state['is_compliant']}

builder = StateGraph(ExtrusionState)
builder.add_node('geom', validate_geometry)
builder.add_node('material', perform_material_analysis)
builder.add_node('final', consolidate_results)

builder.set_entry_point('geom')
builder.add_edge('geom', 'material')
builder.add_edge('material', 'final')
builder.add_edge('final', END)

graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_specs': {},
    'validation_results': [],
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
