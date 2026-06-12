from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ChemicalState(TypedDict):
    commodity_code: str
    purity_check: bool
    safety_clearance: bool
    logistics_status: List[str]

def validate_purity(state: ChemicalState) -> ChemicalState:
    # Simulate high-purity chemical validation logic
    state['purity_check'] = True
    return state

def check_safety(state: ChemicalState) -> ChemicalState:
    # Simulate dangerous goods compliance check
    state['safety_clearance'] = True
    return state

def update_logistics(state: ChemicalState) -> ChemicalState:
    state['logistics_status'].append('ready_for_secure_transport')
    return state

builder = StateGraph(ChemicalState)
builder.add_node('validate_purity', validate_purity)
builder.add_node('check_safety', check_safety)
builder.add_node('update_logistics', update_logistics)
builder.add_edge('validate_purity', 'check_safety')
builder.add_edge('check_safety', 'update_logistics')
builder.add_edge('update_logistics', END)
builder.set_entry_point('validate_purity')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'purity_check': False,
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
