from typing import TypedDict
from langgraph.graph import StateGraph, END

class DispenserState(TypedDict):
    spec_data: dict
    validation_logger: list

def validate_food_safety(state: DispenserState):
    compliance = state['spec_data'].get('food_grade_certification', False)
    log = 'Passed' if compliance else 'Failed: Missing Food Grade Certification'
    return {'validation_logger': [log]}

def check_cooling(state: DispenserState):
    cap = state['spec_data'].get('cooling_capacity_liters_per_hour', 0)
    log = 'Cooling capacity validated' if cap > 0 else 'Error: Low capacity'
    return {'validation_logger': state['validation_logger'] + [log]}

builder = StateGraph(DispenserState)
builder.add_node('validate_safety', validate_food_safety)
builder.add_node('check_cooling', check_cooling)
builder.set_entry_point('validate_safety')
builder.add_edge('validate_safety', 'check_cooling')
builder.add_edge('check_cooling', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_logger': []
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
