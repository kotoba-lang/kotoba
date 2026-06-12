from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    chemical_id: str
    purity_validated: bool
    safety_clearance: bool
    logistics_approved: bool
    messages: Annotated[Sequence[str], operator.add]

def validate_purity(state: ChemicalState) -> ChemicalState:
    # Simulate purity analysis
    state['purity_validated'] = True
    state['messages'] = ['Purity validation passed for ' + state['chemical_id']]
    return state

def check_safety(state: ChemicalState) -> ChemicalState:
    # Simulate safety compliance check
    state['safety_clearance'] = True
    state['messages'] = ['Safety clearance obtained']
    return state

def approve_logistics(state: ChemicalState) -> ChemicalState:
    # Simulate logistics approval
    state['logistics_approved'] = True
    state['messages'] = ['Logistics chain verified']
    return state

graph = StateGraph(ChemicalState)
graph.add_node('purity', validate_purity)
graph.add_node('safety', check_safety)
graph.add_node('logistics', approve_logistics)
graph.set_entry_point('purity')
graph.add_edge('purity', 'safety')
graph.add_edge('safety', 'logistics')
graph.add_edge('logistics', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'chemical_id': "",
    'purity_validated': False,
    'safety_clearance': False,
    'logistics_approved': False,
    'messages': []
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
