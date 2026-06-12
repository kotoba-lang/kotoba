from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class TankState(TypedDict):
    specifications: dict
    validation_results: List[str]
    approved: bool

def validate_pressure_specs(state: TankState):
    pressure = state['specifications'].get('pressure_rating_mpa', 0)
    if pressure > 1.0:
        state['validation_results'].append('High-pressure certification required.')
    return {'validation_results': state['validation_results']}

def check_material_safety(state: TankState):
    material = state['specifications'].get('material_grade', '')
    if 'SUS316' in material:
        state['validation_results'].append('Material compliant with pharma-grade.')
    return {'validation_results': state['validation_results']}

graph = StateGraph(TankState)
graph.add_node('pressure_check', validate_pressure_specs)
graph.add_node('material_check', check_material_safety)
graph.set_entry_point('pressure_check')
graph.add_edge('pressure_check', 'material_check')
graph.add_edge('material_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specifications': {},
    'validation_results': [],
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
