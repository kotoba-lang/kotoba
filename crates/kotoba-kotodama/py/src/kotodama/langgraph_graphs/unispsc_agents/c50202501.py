from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ConcentrateState(TypedDict):
    batch_id: str
    brix_level: float
    is_compliant: bool
    test_results: List[str]

def validate_quality(state: ConcentrateState):
    # Business logic for blackberry concentrate inspection
    if state['brix_level'] > 60:
        return {'is_compliant': True, 'test_results': ['Brix valid', 'Sanitary check passed']}
    else:
        return {'is_compliant': False, 'test_results': ['Brix too low']}

def finish_processing(state: ConcentrateState):
    return {'test_results': state['test_results'] + ['Certification generated']}

graph = StateGraph(ConcentrateState)
graph.add_node('validate', validate_quality)
graph.add_node('finish', finish_processing)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finish')
graph.add_edge('finish', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'brix_level': 0.0,
    'is_compliant': False,
    'test_results': []
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
