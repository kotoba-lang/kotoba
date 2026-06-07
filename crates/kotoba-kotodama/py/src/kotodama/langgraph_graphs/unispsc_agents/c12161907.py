from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MaterialState(TypedDict):
    material_id: str
    purity_level: float
    particle_size: float
    status: str
    validation_log: List[str]

def validate_material(state: MaterialState) -> MaterialState:
    log = state.get('validation_log', [])
    if state['purity_level'] < 99.9:
        state['status'] = 'REJECTED'
        log.append('Purity below 99.9% threshold')
    else:
        state['status'] = 'VALIDATED'
        log.append('Purity check passed')
    state['validation_log'] = log
    return state

def route_by_status(state: MaterialState) -> str:
    return 'process_order' if state['status'] == 'VALIDATED' else 'notify_procurement'

graph = StateGraph(MaterialState)
graph.add_node('validate', validate_material)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity_level': 0.0,
    'particle_size': 0.0,
    'status': "",
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
