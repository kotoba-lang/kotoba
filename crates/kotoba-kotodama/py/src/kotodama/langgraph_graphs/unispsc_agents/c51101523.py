from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    reagent_id: str
    purity_check: bool
    safety_validation: bool
    log: List[str]

def validate_purity(state: ReagentState) -> ReagentState:
    # Simulate chemical purity validation logic
    state['purity_check'] = True
    state['log'].append('Purity verified against specification.')
    return state

def validate_safety(state: ReagentState) -> ReagentState:
    # Simulate SDS and hazardous material compliance
    state['safety_validation'] = True
    state['log'].append('Safety protocols and SDS verified.')
    return state

graph = StateGraph(ReagentState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('validate_safety', validate_safety)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'validate_safety')
graph.add_edge('validate_safety', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'reagent_id': "",
    'purity_check': False,
    'safety_validation': False,
    'log': []
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
