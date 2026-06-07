from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class VacuumMoldState(TypedDict):
    specs: dict
    validation_log: List[str]
    approved: bool

def validate_material(state: VacuumMoldState):
    log = state.get('validation_log', [])
    if 'material_grade' not in state['specs']:
        log.append('Error: Missing Material Grade')
    return {'validation_log': log}

def check_geometry(state: VacuumMoldState):
    log = state.get('validation_log', [])
    if state['specs'].get('thickness', 0) < 0.5:
        log.append('Warning: Thin wall section detected')
    return {'validation_log': log}

graph = StateGraph(VacuumMoldState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_geometry', check_geometry)
graph.add_edge('validate_material', 'check_geometry')
graph.add_edge('check_geometry', END)
graph.set_entry_point('validate_material')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'validation_log': [],
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
