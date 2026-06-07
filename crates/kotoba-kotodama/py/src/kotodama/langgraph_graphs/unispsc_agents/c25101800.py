from typing import TypedDict
from langgraph.graph import StateGraph, END

class CycleState(TypedDict):
    vin: str
    spec_sheet: dict
    approved: bool

def validate_emissions(state: CycleState):
    # Simulate regulatory validation logic for motorized cycles
    state['approved'] = state['spec_sheet'].get('emission_standard') == 'Euro5'
    return state

def check_battery_safety(state: CycleState):
    # Simulate safety inspection for electric components
    if 'battery_capacity_wh' in state['spec_sheet']:
        state['approved'] = state['approved'] and state['spec_sheet']['battery_capacity_wh'] < 5000
    return state

graph = StateGraph(CycleState)
graph.add_node('validate_emissions', validate_emissions)
graph.add_node('check_battery_safety', check_battery_safety)
graph.add_edge('validate_emissions', 'check_battery_safety')
graph.add_edge('check_battery_safety', END)
graph.set_entry_point('validate_emissions')

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'vin': "",
    'spec_sheet': {},
    'approved': False
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
