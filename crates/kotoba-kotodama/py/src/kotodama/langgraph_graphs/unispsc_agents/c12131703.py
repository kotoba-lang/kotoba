from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class SilaneProcessState(TypedDict):
    purity_level: float
    contamination_trace: List[str]
    validation_passed: bool

def validate_purity(state: SilaneProcessState):
    passed = state['purity_level'] >= 99.9999
    return {'validation_passed': passed}

def check_contaminants(state: SilaneProcessState):
    if any('metal' in c for c in state['contamination_trace']):
        return {'validation_passed': False}
    return {'validation_passed': True}

graph = StateGraph(SilaneProcessState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_contaminants', check_contaminants)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_contaminants')
graph.add_edge('check_contaminants', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'contamination_trace': [],
    'validation_passed': False
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
