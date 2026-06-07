from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class HydroformingState(TypedDict):
    part_id: str
    pressure_test_passed: bool
    dimensional_check: bool
    steps: List[str]

def validate_pressure(state: HydroformingState):
    # Simulate hydroforming pressure validation logic
    state['pressure_test_passed'] = True
    state['steps'].append('Pressure check verified')
    return state

def validate_dimensions(state: HydroformingState):
    # Simulate dimensional tolerance check
    state['dimensional_check'] = True
    state['steps'].append('Dimensions within tolerance')
    return state

graph = StateGraph(HydroformingState)
graph.add_node('pressure', validate_pressure)
graph.add_node('dimensions', validate_dimensions)
graph.set_entry_point('pressure')
graph.add_edge('pressure', 'dimensions')
graph.add_edge('dimensions', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'pressure_test_passed': False,
    'dimensional_check': False,
    'steps': []
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
