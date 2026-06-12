from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralFuelState(TypedDict):
    batch_id: str
    gravity_index: float
    sulfur_pct: float
    status: str
    logs: List[str]

def validate_quality(state: MineralFuelState) -> MineralFuelState:
    if state['sulfur_pct'] > 0.5:
        state['status'] = 'REJECTED'
        state['logs'].append('High sulfur content detected')
    else:
        state['status'] = 'CERTIFIED'
    return state

def check_sanctions(state: MineralFuelState) -> MineralFuelState:
    if state['status'] != 'REJECTED':
        state['status'] = 'SANCTION_CLEAR'
    return state

builder = StateGraph(MineralFuelState)
builder.add_node('validate', validate_quality)
builder.add_node('sanctions', check_sanctions)
builder.set_entry_point('validate')
builder.add_edge('validate', 'sanctions')
builder.add_edge('sanctions', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'gravity_index': 0.0,
    'sulfur_pct': 0.0,
    'status': "",
    'logs': []
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
