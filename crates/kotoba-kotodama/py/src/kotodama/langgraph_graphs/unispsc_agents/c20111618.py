from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class HydraulicValveState(TypedDict):
    part_number: str
    specifications: dict
    validation_passed: bool
    log: List[str]

def validate_valve_specs(state: HydraulicValveState) -> HydraulicValveState:
    specs = state.get('specifications', {})
    required = ['max_pressure_rating', 'flow_rate_lpm']
    passed = all(k in specs for k in required)
    state['validation_passed'] = passed
    state['log'].append(f'Validation: {passed}')
    return state

def check_dual_use(state: HydraulicValveState) -> HydraulicValveState:
    state['log'].append('Checking export control compliance for high-pressure components')
    return state

graph = StateGraph(HydraulicValveState)
graph.add_node('validate', validate_valve_specs)
graph.add_node('compliance', check_dual_use)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'specifications': {},
    'validation_passed': False,
    'log': []
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
