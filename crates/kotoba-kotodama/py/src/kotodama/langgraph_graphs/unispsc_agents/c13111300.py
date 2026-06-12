from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class GasState(TypedDict):
    commodity_code: str
    purity_level: float
    pressure: float
    safety_check_passed: bool
    logs: Annotated[Sequence[str], operator.add]

def validate_composition(state: GasState):
    if state['purity_level'] < 0.99:
        return {'logs': ['Purity low, triggering re-refinement']}
    return {'logs': ['Purity acceptable']}

def check_infrastructure(state: GasState):
    if state['pressure'] > 5000:
        return {'logs': ['Pressure exceeding safety limits'], 'safety_check_passed': False}
    return {'logs': ['Infrastructure secure'], 'safety_check_passed': True}

graph = StateGraph(GasState)
graph.add_node('validate', validate_composition)
graph.add_node('safety', check_infrastructure)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'purity_level': 0.0,
    'pressure': 0.0,
    'safety_check_passed': False,
    'logs': []
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
