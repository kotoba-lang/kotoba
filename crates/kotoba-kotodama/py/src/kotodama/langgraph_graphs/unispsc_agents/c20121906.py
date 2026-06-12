from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    part_id: str
    specs: dict
    validation_log: List[str]
    is_approved: bool

def validate_load_capacity(state: BearingState):
    load = state['specs'].get('load_capacity_rating', 0)
    if load > 500:
        state['validation_log'].append('High capacity verified.')
    return {'validation_log': state['validation_log']}

def check_material_compliance(state: BearingState):
    material = state['specs'].get('material', '')
    if material == 'Al-6061-T6':
        state['validation_log'].append('Material standard met.')
        state['is_approved'] = True
    return {'validation_log': state['validation_log'], 'is_approved': state['is_approved']}

graph = StateGraph(BearingState)
graph.add_node('validate_load', validate_load_capacity)
graph.add_node('check_material', check_material_compliance)
graph.add_edge('validate_load', 'check_material')
graph.add_edge('check_material', END)
graph.set_entry_point('validate_load')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'specs': {},
    'validation_log': [],
    'is_approved': False
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
