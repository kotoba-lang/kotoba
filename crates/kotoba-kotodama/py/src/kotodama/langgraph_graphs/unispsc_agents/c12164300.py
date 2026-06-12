from typing import TypedDict, List, Annotated
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    catalyst_id: str
    purity_level: float
    validation_checks: Annotated[List[str], operator.add]
    is_approved: bool

def validate_catalyst_purity(state: CatalystState):
    if state['purity_level'] >= 99.9:
        return {'validation_checks': ['High-purity standard met'], 'is_approved': True}
    return {'validation_checks': ['Purity insufficient for procurement'], 'is_approved': False}

def check_hazard_compliance(state: CatalystState):
    return {'validation_checks': ['Hazardous materials handling cleared']}

graph = StateGraph(CatalystState)
graph.add_node('validate_purity', validate_catalyst_purity)
graph.add_node('check_hazards', check_hazard_compliance)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_hazards')
graph.add_edge('check_hazards', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'catalyst_id': "",
    'purity_level': 0.0,
    'validation_checks': [],
    'is_approved': False
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
