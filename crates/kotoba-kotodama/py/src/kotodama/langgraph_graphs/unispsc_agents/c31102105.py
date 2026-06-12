from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastState(TypedDict):
    part_id: str
    material_spec: str
    tolerance_passed: bool
    approved: bool

def validate_material(state: CastState) -> CastState:
    # Logic to verify casting material composition
    state['material_spec'] = 'Verified' if state['material_spec'] else 'Missing'
    return state

def validate_tolerance(state: CastState) -> CastState:
    # Logic to verify dimension measurements
    state['tolerance_passed'] = True
    return state

graph = StateGraph(CastState)
graph.add_node('MaterialCheck', validate_material)
graph.add_node('ToleranceCheck', validate_tolerance)
graph.set_entry_point('MaterialCheck')
graph.add_edge('MaterialCheck', 'ToleranceCheck')
graph.add_edge('ToleranceCheck', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'material_spec': "",
    'tolerance_passed': False,
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
