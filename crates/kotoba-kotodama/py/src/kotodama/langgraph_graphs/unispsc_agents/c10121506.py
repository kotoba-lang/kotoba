from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class FertilizerState(TypedDict):
    input_data: dict
    analysis_results: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_composition(state: FertilizerState):
    input_data = state['input_data']
    results = []
    compliant = True
    if input_data.get('heavy_metals', 0) > 0.05:
        results.append('High heavy metal content')
        compliant = False
    return {'analysis_results': results, 'is_compliant': compliant}

def route_by_compliance(state: FertilizerState):
    return 'process' if state['is_compliant'] else END

def process_fertilizer_order(state: FertilizerState):
    return {'analysis_results': ['Composition validated and cleared for procurement']}

graph = StateGraph(FertilizerState)
graph.add_node('validate', validate_composition)
graph.add_node('process', process_fertilizer_order)
graph.add_edge('validate', 'process')
graph.add_conditional_edges('validate', route_by_compliance, {'process': 'process', '__end__': END})
graph.set_entry_point('validate')
graph.add_edge('process', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'input_data': {},
    'analysis_results': [],
    'is_compliant': False
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
