from typing import TypedDict, Annotated, Sequence, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class NitrogenProcurementState(TypedDict):
    purity: float
    volume: float
    is_liquid: bool
    validation_logs: List[str]
    approved: bool

def validate_purity(state: NitrogenProcurementState) -> NitrogenProcurementState:
    if state['purity'] < 99.9:
        state['validation_logs'].append('Low purity: requires additional purification steps.')
    else:
        state['validation_logs'].append('Purity check passed.')
    return state

def safety_protocol_check(state: NitrogenProcurementState) -> NitrogenProcurementState:
    if state['is_liquid']:
        state['validation_logs'].append('Handling as cryogenic dangerous good.')
    else:
        state['validation_logs'].append('Standard gas pressure check.')
    state['approved'] = True
    return state

builder = StateGraph(NitrogenProcurementState)
builder.add_node('validate_purity', validate_purity)
builder.add_node('safety_check', safety_protocol_check)
builder.add_edge('validate_purity', 'safety_check')
builder.add_edge('safety_check', END)
builder.set_entry_point('validate_purity')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'volume': 0.0,
    'is_liquid': False,
    'validation_logs': [],
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
