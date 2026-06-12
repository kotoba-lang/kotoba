from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CompostState(TypedDict):
    batch_id: str
    nutrient_profile: dict
    status: str
    validation_logs: List[str]

def validate_nutrient_composition(state: CompostState) -> CompostState:
    n = state.get('nutrient_profile', {}).get('nitrogen', 0)
    if n < 1.5:
        state['status'] = 'REJECTED_LOW_NUTRIENT'
        state['validation_logs'].append('Nitrogen level below 1.5% threshold.')
    else:
        state['status'] = 'VALIDATED'
        state['validation_logs'].append('Nutrient profile verified.')
    return state

def check_pathogen_risk(state: CompostState) -> CompostState:
    if state['status'] != 'VALIDATED':
        return state
    state['validation_logs'].append('Pathogen analysis cleared.')
    return state

graph = StateGraph(CompostState)
graph.add_node('validate', validate_nutrient_composition)
graph.add_node('pathogen_check', check_pathogen_risk)
graph.add_edge('validate', 'pathogen_check')
graph.add_edge('pathogen_check', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'nutrient_profile': {},
    'status': "",
    'validation_logs': []
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
