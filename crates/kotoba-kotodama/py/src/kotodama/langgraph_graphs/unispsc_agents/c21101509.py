from typing import TypedDict
from langgraph.graph import StateGraph, END

class TractorState(TypedDict):
    specs: dict
    approved: bool
    validation_log: list

def validate_emissions(state: TractorState):
    emission_tier = state['specs'].get('engine_emission_standard')
    is_valid = emission_tier in ['Tier4', 'StageV']
    return {'approved': is_valid, 'validation_log': [f'Emission check: {is_valid}']}

def check_towing_capacity(state: TractorState):
    capacity = state['specs'].get('towing_capacity_kg', 0)
    valid = capacity > 1000
    return {'approved': state['approved'] and valid, 'validation_log': state['validation_log'] + [f'Towing check: {valid}']}

graph = StateGraph(TractorState)
graph.add_node('validate_emissions', validate_emissions)
graph.add_node('check_towing_capacity', check_towing_capacity)
graph.set_entry_point('validate_emissions')
graph.add_edge('validate_emissions', 'check_towing_capacity')
graph.add_edge('check_towing_capacity', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'approved': False,
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
