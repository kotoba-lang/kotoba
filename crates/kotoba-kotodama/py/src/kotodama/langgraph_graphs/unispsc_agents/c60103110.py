from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class GeometrySpecState(TypedDict):
    material: str
    tolerance: float
    is_compliant: bool
    validation_log: List[str]

def validate_material(state: GeometrySpecState):
    state['validation_log'].append(f'Checking material: {state['material']}')
    return {'is_compliant': state['material'] in ['polycarbonate', 'aluminum']}

def validate_tolerance(state: GeometrySpecState):
    state['validation_log'].append(f'Checking tolerance: {state['tolerance']}')
    return {'is_compliant': state['tolerance'] <= 0.05}

graph = StateGraph(GeometrySpecState)
graph.add_node('material_check', validate_material)
graph.add_node('tolerance_check', validate_tolerance)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'tolerance_check')
graph.add_edge('tolerance_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material': "",
    'tolerance': 0.0,
    'is_compliant': False,
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
