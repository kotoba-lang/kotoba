from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralState(TypedDict):
    commodity_code: str
    purity: float
    origin: str
    validation_passed: bool
    error_logs: List[str]

def validate_purity(state: MineralState) -> MineralState:
    if state['purity'] < 95.0:
        state['validation_passed'] = False
        state['error_logs'].append('Purity below 95% threshold')
    else:
        state['validation_passed'] = True
    return state

def check_sanctions(state: MineralState) -> MineralState:
    if state['origin'] in ['RestrictedRegionA', 'RestrictedRegionB']:
        state['validation_passed'] = False
        state['error_logs'].append('Origin under export sanction')
    return state

graph = StateGraph(MineralState)
graph.add_node('validate', validate_purity)
graph.add_node('sanctions', check_sanctions)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sanctions')
graph.add_edge('sanctions', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'purity': 0.0,
    'origin': "",
    'validation_passed': False,
    'error_logs': []
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
