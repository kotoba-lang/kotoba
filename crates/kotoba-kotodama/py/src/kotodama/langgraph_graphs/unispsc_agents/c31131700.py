from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    part_specs: dict
    validation_passed: bool

def validate_geometry(state: ForgingState):
    # Simulate CAD geometry validation logic
    state['validation_passed'] = 'tolerance' in state['part_specs']
    return state

def check_material_cert(state: ForgingState):
    # logic to verify metallurgical certification
    return {'validation_passed': state['validation_passed'] and 'cert' in state['part_specs']}

graph = StateGraph(ForgingState)
graph.add_node('validate_geometry', validate_geometry)
graph.add_node('check_material_cert', check_material_cert)
graph.add_edge('validate_geometry', 'check_material_cert')
graph.add_edge('check_material_cert', END)
graph.set_entry_point('validate_geometry')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_specs': {},
    'validation_passed': False
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
