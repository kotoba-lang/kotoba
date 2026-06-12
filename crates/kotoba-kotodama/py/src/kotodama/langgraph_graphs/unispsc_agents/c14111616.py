from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class FolderState(TypedDict):
    folder_id: str
    spec: dict
    validation_log: List[str]
    is_compliant: bool

def validate_spec(state: FolderState) -> FolderState:
    spec = state['spec']
    logs = []
    if spec.get('paper_weight_gsm', 0) < 150:
        logs.append('Insufficient paper weight for standard folders.')
    state['validation_log'] = logs
    state['is_compliant'] = len(logs) == 0
    return state

def check_dimensions(state: FolderState) -> FolderState:
    if not state.get('is_compliant', False):
        return state
    dims = state['spec'].get('dimensions_mm', {})
    if dims.get('width', 0) < 220 or dims.get('height', 0) < 300:
        state['validation_log'].append('Dimensions below standard A4/Letter size.')
        state['is_compliant'] = False
    return state

builder = StateGraph(FolderState)
builder.add_node('validate', validate_spec)
builder.add_node('check_dims', check_dimensions)
builder.add_edge('validate', 'check_dims')
builder.add_edge('check_dims', END)
builder.set_entry_point('validate')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'folder_id': "",
    'spec': {},
    'validation_log': [],
    'is_compliant': False
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
