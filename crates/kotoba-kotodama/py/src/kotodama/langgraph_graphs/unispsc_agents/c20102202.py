from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class AgitatorShaftState(TypedDict):
    shaft_id: str
    material_grade: str
    spec_check_passed: bool
    inspection_result: str

def validate_material(state: AgitatorShaftState):
    # Verify material meets industrial standards
    passed = state['material_grade'] in ['SUS304', 'SUS316L', 'Titanium']
    return {'spec_check_passed': passed, 'inspection_result': 'Material Validated' if passed else 'Material Rejected'}

def perform_inspection(state: AgitatorShaftState):
    if not state['spec_check_passed']:
        return {'inspection_result': 'Skipped due to material failure'}
    return {'inspection_result': 'Dimensional tolerance verified, surface finish within spec'}

graph = StateGraph(AgitatorShaftState)
graph.add_node('validate_material', validate_material)
graph.add_node('perform_inspection', perform_inspection)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'perform_inspection')
graph.add_edge('perform_inspection', END)

# Compile the graph
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'shaft_id': "",
    'material_grade': "",
    'spec_check_passed': False,
    'inspection_result': ""
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
