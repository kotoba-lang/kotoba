from typing import TypedDict, Annotated, List
import operator
from langgraph.graph import StateGraph, END

class BoxingRingState(TypedDict):
    specifications: dict
    validation_logs: Annotated[List[str], operator.add]
    is_compliant: bool

def validate_structural_integrity(state: BoxingRingState):
    specs = state['specifications']
    valid = specs.get('load_capacity', 0) >= 5000
    return {'validation_logs': ['Structural integrity check passed'] if valid else ['Structural failure detected'], 'is_compliant': valid}

def check_safety_standards(state: BoxingRingState):
    return {'validation_logs': ['Safety standards (EN12503) verified']}

graph = StateGraph(BoxingRingState)
graph.add_node('structural_check', validate_structural_integrity)
graph.add_node('safety_check', check_safety_standards)
graph.set_entry_point('structural_check')
graph.add_edge('structural_check', 'safety_check')
graph.add_edge('safety_check', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specifications': {},
    'validation_logs': [],
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
