from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PistonState(TypedDict):
    specifications: dict
    validation_passed: bool
    inspection_report: str

def validate_materials(state: PistonState):
    print('Validating thermal and mechanical properties...')
    state['validation_passed'] = 'material_grade' in state['specifications']
    return state

def run_tolerance_check(state: PistonState):
    print('Performing precision diameter analysis...')
    return {'inspection_report': 'Dimensions within tolerance range'}

graph = StateGraph(PistonState)
graph.add_node('material_check', validate_materials)
graph.add_node('tolerance_test', run_tolerance_check)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'tolerance_test')
graph.add_edge('tolerance_test', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specifications': {},
    'validation_passed': False,
    'inspection_report': ""
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
