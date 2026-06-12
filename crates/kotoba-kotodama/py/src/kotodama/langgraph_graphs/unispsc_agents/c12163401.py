from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    purity_level: float
    safety_score: float
    compliance_validated: bool
    history: List[str]

def validate_purity(state: ChemicalState):
    if state['purity_level'] >= 0.98:
        return {'compliance_validated': True, 'history': state['history'] + ['Purity OK']}
    return {'compliance_validated': False, 'history': state['history'] + ['Purity Low']}

def safety_check(state: ChemicalState):
    if state['safety_score'] > 8.5:
        return {'history': state['history'] + ['Safety Certified']}
    return {'history': state['history'] + ['Safety Review Required']}

graph = StateGraph(ChemicalState)
graph.add_node('purity_check', validate_purity)
graph.add_node('safety_check', safety_check)
graph.set_entry_point('purity_check')
graph.add_edge('purity_check', 'safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'safety_score': 0.0,
    'compliance_validated': False,
    'history': []
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
