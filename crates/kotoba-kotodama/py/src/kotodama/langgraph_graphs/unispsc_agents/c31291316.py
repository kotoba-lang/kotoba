from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TitaniumPartState(TypedDict):
    part_id: str
    material_spec: str
    dimension_check: bool
    compliance_tags: List[str]

def validate_materials(state: TitaniumPartState):
    # Simulate material compliance check for aerospace grade titanium
    state['material_spec'] = 'Certified Grade 5' if state['part_id'] else 'Unknown'
    return state

def check_dimensions(state: TitaniumPartState):
    # Logic to verify cold extrusion tolerances
    state['dimension_check'] = True
    return state

graph = StateGraph(TitaniumPartState)
graph.add_node('validate', validate_materials)
graph.add_node('dimensions', check_dimensions)
graph.set_entry_point('validate')
graph.add_edge('validate', 'dimensions')
graph.add_edge('dimensions', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'material_spec': "",
    'dimension_check': False,
    'compliance_tags': []
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
