from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MountingBaseState(TypedDict):
    part_id: str
    pressure_rating: float
    material_certified: bool
    validation_log: List[str]

def validate_load_specs(state: MountingBaseState):
    if state['pressure_rating'] > 500:
        state['validation_log'].append('High pressure load validation passed.')
    else:
        state['validation_log'].append('Standard pressure load validation.')
    return {'validation_log': state['validation_log']}

def check_compliance(state: MountingBaseState):
    if state['material_certified']:
        state['validation_log'].append('Material certification verified.')
    return {'validation_log': state['validation_log']}

graph = StateGraph(MountingBaseState)
graph.add_node('validate_load', validate_load_specs)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('validate_load')
graph.add_edge('validate_load', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'pressure_rating': 0.0,
    'material_certified': False,
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
