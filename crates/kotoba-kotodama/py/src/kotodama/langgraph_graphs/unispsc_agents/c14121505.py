from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class FolderState(TypedDict):
    item_id: str
    material: str
    thickness: float
    is_compliant: bool
    validation_log: List[str]

def validate_material(state: FolderState):
    log = state.get('validation_log', [])
    if state['material'] in ['paper', 'plastic']:
        log.append(f'Material {state["material"]} is valid.')
        return {'is_compliant': True, 'validation_log': log}
    return {'is_compliant': False, 'validation_log': log + ['Invalid material type.']}

def check_dimensions(state: FolderState):
    log = state.get('validation_log', [])
    if state['thickness'] > 0.1:
        log.append('Thickness meets standard.')
        return {'validation_log': log}
    return {'is_compliant': False, 'validation_log': log + ['Insufficient thickness.']}

graph = StateGraph(FolderState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_dimensions', check_dimensions)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'check_dimensions')
graph.add_edge('check_dimensions', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'item_id': "",
    'material': "",
    'thickness': 0.0,
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
