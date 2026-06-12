from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TrainingState(TypedDict):
    material_type: str
    participant_count: int
    is_digital: bool
    validation_errors: List[str]

def validate_materials(state: TrainingState):
    errors = []
    if not state.get('material_type'):
        errors.append('Missing material type')
    return {'validation_errors': errors}

def route_by_type(state: TrainingState):
    return 'process_digital' if state['is_digital'] else 'process_physical'

graph = StateGraph(TrainingState)
graph.add_node('validate', validate_materials)
graph.add_node('process_digital', lambda s: s)
graph.add_node('process_physical', lambda s: s)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_type)
graph.add_edge('process_digital', END)
graph.add_edge('process_physical', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_type': "",
    'participant_count': 0,
    'is_digital': False,
    'validation_errors': []
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
