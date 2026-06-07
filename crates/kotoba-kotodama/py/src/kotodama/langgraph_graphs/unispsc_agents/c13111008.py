from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class MetalProcurementState(TypedDict):
    material_spec: dict
    validation_results: Annotated[List[str], operator.add]
    is_approved: bool

def validate_composition(state: MetalProcurementState):
    spec = state['material_spec']
    if 'alloy_composition_percent' in spec and spec['alloy_composition_percent'] > 99.0:
        return {'validation_results': ['Composition high purity verified'], 'is_approved': True}
    return {'validation_results': ['Composition check failed'], 'is_approved': False}

def check_compliance(state: MetalProcurementState):
    if state.get('is_approved'):
        return {'validation_results': ['Compliance standards met']}
    return {'validation_results': ['Compliance verification pending']}

graph = StateGraph(MetalProcurementState)
graph.add_node('validate', validate_composition)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_spec': {},
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
