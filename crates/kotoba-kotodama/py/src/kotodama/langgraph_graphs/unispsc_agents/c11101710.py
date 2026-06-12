from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralState(TypedDict):
    mineral_id: str
    purity_level: float
    inspection_passed: bool
    history_log: List[str]

def validate_purity(state: MineralState):
    passed = state['purity_level'] > 0.98
    return {'inspection_passed': passed, 'history_log': state['history_log'] + ['Purity validation completed']}

def update_registry(state: MineralState):
    if state['inspection_passed']:
        return {'history_log': state['history_log'] + ['Logged into central supply registry']}
    return {'history_log': state['history_log'] + ['Failed validation - flagged']}

graph = StateGraph(MineralState)
graph.add_node('validate', validate_purity)
graph.add_node('registry', update_registry)
graph.add_edge('validate', 'registry')
graph.set_entry_point('validate')
graph.add_edge('registry', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'mineral_id': "",
    'purity_level': 0.0,
    'inspection_passed': False,
    'history_log': []
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
