from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ReflectorState(TypedDict):
    material: str
    reflectivity: float
    status: str

def validate_reflectivity(state: ReflectorState):
    if state['reflectivity'] < 0.90:
        return {'status': 'rejected'}
    return {'status': 'approved'}

def check_material(state: ReflectorState):
    allowed = ['Aluminum', 'Silver', 'Polished Steel']
    if state['material'] in allowed:
        return {'status': 'material_accepted'}
    return {'status': 'invalid_material'}

graph = StateGraph(ReflectorState)
graph.add_node('check_material', check_material)
graph.add_node('validate_reflectivity', validate_reflectivity)
graph.set_entry_point('check_material')
graph.add_edge('check_material', 'validate_reflectivity')
graph.add_edge('validate_reflectivity', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material': "",
    'reflectivity': 0.0,
    'status': ""
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
