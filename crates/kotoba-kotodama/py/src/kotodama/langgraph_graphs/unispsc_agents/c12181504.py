from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ResinProcessingState(TypedDict):
    material_specs: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_safety_compliance(state: ResinProcessingState):
    # Simulate chemical safety data validation
    is_safe = 'msds' in state['material_specs'] and 'hazard_level' in state['material_specs']
    return {'validation_results': ['Safety validation passed'] if is_safe else ['Safety validation failed']}

def check_technical_specs(state: ResinProcessingState):
    # Simulate viscosity and curing parameter validation
    is_valid = state['material_specs'].get('viscosity') and state['material_specs'].get('curing_temp')
    return {'validation_results': ['Specs validation passed'] if is_valid else ['Specs validation failed']}

def approve_procurement(state: ResinProcessingState):
    return {'is_approved': 'Safety validation passed' in state['validation_results'] and 'Specs validation passed' in state['validation_results']}

graph = StateGraph(ResinProcessingState)
graph.add_node('safety_check', validate_safety_compliance)
graph.add_node('spec_check', check_technical_specs)
graph.add_node('approval', approve_procurement)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'spec_check')
graph.add_edge('spec_check', 'approval')
graph.add_edge('approval', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_specs': {},
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
