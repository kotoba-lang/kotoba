from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ToolProcessState(TypedDict):
    tool_id: str
    material_hardness: float
    inspection_passed: bool
    validation_log: list[str]

def validate_material_compatibility(state: ToolProcessState) -> ToolProcessState:
    if state['material_hardness'] > 8.0:
        state['validation_log'].append('Hardness within operational limits.')
        state['inspection_passed'] = True
    else:
        state['validation_log'].append('Material too soft for diamond tooling.')
        state['inspection_passed'] = False
    return state

def execute_grinding_simulation(state: ToolProcessState) -> ToolProcessState:
    if state['inspection_passed']:
        state['validation_log'].append('Grinding simulation successful.')
    return state

graph = StateGraph(ToolProcessState)
graph.add_node('validate', validate_material_compatibility)
graph.add_node('grind', execute_grinding_simulation)
graph.add_edge('validate', 'grind')
graph.add_edge('grind', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'tool_id': "",
    'material_hardness': 0.0,
    'inspection_passed': False,
    'validation_log': []
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
