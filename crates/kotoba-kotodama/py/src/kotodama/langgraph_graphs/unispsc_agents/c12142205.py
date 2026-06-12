from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    commodity_id: str
    purity_level: float
    safety_clearance: bool
    logistics_status: List[str]

def validate_purity(state: ChemicalState) -> ChemicalState:
    if state['purity_level'] < 99.5:
        state['logistics_status'].append('PURITY_REJECTED')
    else:
        state['logistics_status'].append('PURITY_VERIFIED')
    return state

def check_safety_protocols(state: ChemicalState) -> ChemicalState:
    if state['safety_clearance']:
        state['logistics_status'].append('SAFETY_APPROVED')
    else:
        state['logistics_status'].append('SAFETY_HOLD')
    return state

builder = StateGraph(ChemicalState)
builder.add_node('validate_purity', validate_purity)
builder.add_node('check_safety', check_safety_protocols)
builder.set_entry_point('validate_purity')
builder.add_edge('validate_purity', 'check_safety')
builder.add_edge('check_safety', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_id': "",
    'purity_level': 0.0,
    'safety_clearance': False,
    'logistics_status': []
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
