from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    assembly_specs: dict
    validation_passed: bool
    errors: List[str]

def validate_materials(state: ProcessingState):
    specs = state.get('assembly_specs', {})
    if 'material' not in specs:
        state['errors'].append('Missing material type')
        state['validation_passed'] = False
    return state

def check_joining_compliance(state: ProcessingState):
    if state.get('validation_passed', True):
        print('Checking brazing/welding integrity standards...')
    return state

graph = StateGraph(ProcessingState)
graph.add_node('material_check', validate_materials)
graph.add_node('integrity_check', check_joining_compliance)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'integrity_check')
graph.add_edge('integrity_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'assembly_specs': {},
    'validation_passed': False,
    'errors': []
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
