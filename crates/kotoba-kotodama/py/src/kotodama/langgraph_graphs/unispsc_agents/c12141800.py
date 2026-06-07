from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MaterialState(TypedDict):
    material_id: str
    purity: float
    safety_clearance: bool
    log_steps: List[str]

def validate_material(state: MaterialState) -> MaterialState:
    if state['purity'] >= 99.9:
        state['safety_clearance'] = True
        state['log_steps'].append('Purity validation passed')
    else:
        state['safety_clearance'] = False
        state['log_steps'].append('Purity validation failed')
    return state

def route_by_clearance(state: MaterialState) -> str:
    return 'process' if state['safety_clearance'] else 'reject'

graph = StateGraph(MaterialState)
graph.add_node('validate', validate_material)
graph.add_node('process', lambda s: s)
graph.add_node('reject', lambda s: s)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_clearance)
graph.add_edge('process', END)
graph.add_edge('reject', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity': 0.0,
    'safety_clearance': False,
    'log_steps': []
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
