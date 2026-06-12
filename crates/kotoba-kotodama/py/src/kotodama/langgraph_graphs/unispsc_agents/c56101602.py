from typing import TypedDict
from langgraph.graph import StateGraph, END

class OutdoorChairState(TypedDict):
    spec_data: dict
    validation_results: list
    is_approved: bool

def validate_material(state: OutdoorChairState):
    material = state['spec_data'].get('material')
    valid = material in ['aluminum', 'synthetic_resin', 'teak', 'powder_coated_steel']
    return {'validation_results': [f'Material valid: {valid}']}

def check_durability(state: OutdoorChairState):
    rating = state['spec_data'].get('load_rating', 0)
    return {'is_approved': rating >= 150}

graph = StateGraph(OutdoorChairState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_durability', check_durability)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'check_durability')
graph.add_edge('check_durability', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_results': [],
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
