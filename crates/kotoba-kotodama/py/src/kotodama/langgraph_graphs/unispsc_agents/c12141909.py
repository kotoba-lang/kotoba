from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, END

class PolysiliconState(TypedDict):
    purity: float
    dopant_level: float
    status: str
    validation_log: List[str]

def validate_purity(state: PolysiliconState) -> PolysiliconState:
    if state['purity'] >= 99.9999999:
        state['status'] = 'HIGH_GRADE'
        state['validation_log'].append('Purity validated: Electronic Grade')
    else:
        state['status'] = 'REJECTED'
        state['validation_log'].append('Purity below threshold')
    return state

def check_dopant(state: PolysiliconState) -> PolysiliconState:
    if state['status'] == 'HIGH_GRADE':
        if state['dopant_level'] < 0.001:
            state['status'] = 'APPROVED'
            state['validation_log'].append('Dopant level within specs')
        else:
            state['status'] = 'REJECTED'
            state['validation_log'].append('Dopant level exceeded')
    return state

graph = StateGraph(PolysiliconState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_dopant', check_dopant)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_dopant')
graph.add_edge('check_dopant', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'dopant_level': 0.0,
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
