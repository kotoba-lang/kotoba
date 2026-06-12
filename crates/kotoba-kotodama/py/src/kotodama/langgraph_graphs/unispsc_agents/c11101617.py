from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class MetalAdditiveState(TypedDict):
    material_code: str
    purity_level: float
    safety_check_passed: bool
    log: Annotated[List[str], operator.add]

def validate_purity(state: MetalAdditiveState) -> MetalAdditiveState:
    if state['purity_level'] < 0.99:
        return {'log': ['Purity check failed: below 99% threshold']}
    return {'safety_check_passed': True, 'log': ['Purity verified']}

def perform_safety_screening(state: MetalAdditiveState) -> MetalAdditiveState:
    if state['material_code'].startswith('11'):
        return {'log': ['Material passed hazardous material screening']}
    return {'log': ['Material failed safety screening']}

graph = StateGraph(MetalAdditiveState)
graph.add_node('validate', validate_purity)
graph.add_node('screen', perform_safety_screening)
graph.add_edge('validate', 'screen')
graph.add_edge('screen', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_code': "",
    'purity_level': 0.0,
    'safety_check_passed': False,
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
