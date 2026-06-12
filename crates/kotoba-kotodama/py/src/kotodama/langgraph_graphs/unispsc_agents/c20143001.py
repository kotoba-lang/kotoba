from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class ShaftState(TypedDict):
    specs: dict
    validation_results: Annotated[list, operator.add]
    is_approved: bool

def validate_specs(state: ShaftState):
    results = []
    if state['specs'].get('hardness') < 50:
        results.append('Hardness failure')
    return {'validation_results': results}

def decision_node(state: ShaftState):
    return 'approved' if not state['validation_results'] else 'manual_review'

graph = StateGraph(ShaftState)
graph.add_node('validate', validate_specs)
graph.add_node('manual_review', lambda x: x)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', decision_node, {'approved': END, 'manual_review': 'manual_review'})
graph.add_edge('manual_review', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'validation_results': [],
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
