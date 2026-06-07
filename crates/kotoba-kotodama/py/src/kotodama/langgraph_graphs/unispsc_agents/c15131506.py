from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class FastenerState(TypedDict):
    part_id: str
    material_grade: str
    spec_compliance: bool
    inspection_result: str

def validate_material(state: FastenerState) -> FastenerState:
    # Logic to verify material grade against industry standards
    state['spec_compliance'] = state['material_grade'] in ['Grade 8.8', 'Grade 10.9']
    return state

def run_inspection(state: FastenerState) -> FastenerState:
    # Logic for mechanical inspection simulation
    if state['spec_compliance']:
        state['inspection_result'] = 'PASSED_MECHANICAL_TEST'
    else:
        state['inspection_result'] = 'FAILED_MATERIAL_GRADE'
    return state

graph = StateGraph(FastenerState)
graph.add_node('validate', validate_material)
graph.add_node('inspect', run_inspection)
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'material_grade': "",
    'spec_compliance': False,
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
