from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class BioReagentState(TypedDict):
    lot_id: str
    purity: float
    temp_log: Annotated[list[float], operator.add]
    is_validated: bool

def validate_purity(state: BioReagentState):
    # Perform specialized purity validation logic
    state['is_validated'] = state['purity'] >= 99.0
    return state

def check_temp_stability(state: BioReagentState):
    # Check cold chain integrity
    valid = all(t >= 2.0 and t <= 8.0 for t in state['temp_log'])
    state['is_validated'] = state['is_validated'] and valid
    return state

graph = StateGraph(BioReagentState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_temp_stability', check_temp_stability)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_temp_stability')
graph.add_edge('check_temp_stability', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'lot_id': "",
    'purity': 0.0,
    'temp_log': [],
    'is_validated': False
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
