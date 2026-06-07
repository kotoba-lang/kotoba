from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SemiconductorPartState(TypedDict):
    part_id: str
    spec_requirements: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_purity(state: SemiconductorPartState):
    purity = state['spec_requirements'].get('purity_percentage', 0)
    if purity >= 99.999:
        return {'validation_logs': ['Purity check passed'], 'is_compliant': True}
    return {'validation_logs': ['Purity check failed: substandard grade'], 'is_compliant': False}

def structural_integrity_check(state: SemiconductorPartState):
    # Simulate CAD/Tolerance validation logic
    tolerance = state['spec_requirements'].get('dimensional_tolerance_microns', 10)
    if tolerance <= 5:
        return {'validation_logs': ['Structural integrity verified'], 'is_compliant': True}
    return {'validation_logs': ['Structural tolerance out of range'], 'is_compliant': False}

def build_graph():
    graph = StateGraph(SemiconductorPartState)
    graph.add_node('purity_check', validate_purity)
    graph.add_node('structural_check', structural_integrity_check)
    graph.set_entry_point('purity_check')
    graph.add_edge('purity_check', 'structural_check')
    graph.add_edge('structural_check', END)
    return graph.compile()

graph = build_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'spec_requirements': {},
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
