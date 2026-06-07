from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AnimalProcurementState(TypedDict):
    animal_id: str
    quarantine_status: str
    health_checks: List[str]
    transport_approved: bool

def check_quarantine(state: AnimalProcurementState) -> AnimalProcurementState:
    state['quarantine_status'] = 'verified' if 'passed' in state['health_checks'] else 'pending'
    return state

def validate_transport(state: AnimalProcurementState) -> AnimalProcurementState:
    state['transport_approved'] = state['quarantine_status'] == 'verified'
    return state

graph = StateGraph(AnimalProcurementState)
graph.add_node('quarantine', check_quarantine)
graph.add_node('transport', validate_transport)
graph.add_edge('quarantine', 'transport')
graph.add_edge('transport', END)
graph.set_entry_point('quarantine')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'animal_id': "",
    'quarantine_status': "",
    'health_checks': [],
    'transport_approved': False
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
