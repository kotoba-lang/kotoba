from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class WindowState(TypedDict):
    dimensions: dict
    material: str
    compliance_check: bool
    validation_logs: List[str]

def validate_dimensions(state: WindowState):
    width = state['dimensions'].get('width', 0)
    height = state['dimensions'].get('height', 0)
    is_valid = 500 < width < 3000 and 500 < height < 3000
    return {'compliance_check': is_valid, 'validation_logs': ['Dimensions checked']}

def check_material_specs(state: WindowState):
    valid_materials = ['aluminum', 'vinyl', 'wood', 'fiberglass']
    return {'compliance_check': state['material'] in valid_materials, 'validation_logs': state['validation_logs'] + ['Material checked']}

graph = StateGraph(WindowState)
graph.add_node('validate', validate_dimensions)
graph.add_node('spec_review', check_material_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', 'spec_review')
graph.add_edge('spec_review', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'dimensions': {},
    'material': "",
    'compliance_check': False,
    'validation_logs': []
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
