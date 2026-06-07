from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ChemicalProcessingState(TypedDict):
    commodity_code: str
    purity_level: float
    stability_check: bool
    safety_clearance: bool

def validate_purity(state: ChemicalProcessingState):
    # Simulate CAD/Spec validation for chemical intermediate
    is_pure = state['purity_level'] >= 0.99
    return {'purity_level': state['purity_level'], 'stability_check': is_pure}

def perform_safety_scan(state: ChemicalProcessingState):
    # Compliance check for dual-use/regulated goods
    return {'safety_clearance': True}

graph = StateGraph(ChemicalProcessingState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('safety_scan', perform_safety_scan)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'safety_scan')
graph.add_edge('safety_scan', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'purity_level': 0.0,
    'stability_check': False,
    'safety_clearance': False
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
