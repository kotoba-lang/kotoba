from typing import TypedDict
from langgraph.graph import StateGraph, END
class BackRestState(TypedDict):
    spec_data: dict
    approved: bool
    validation_errors: list
def validate_ergonomic_specs(state: BackRestState):
    errors = []
    if state['spec_data'].get('adjustability_range', 0) < 5:
        errors.append('Adjustability range below ergonomic standard.')
    return {'validation_errors': errors, 'approved': len(errors) == 0}
def safety_compliance_check(state: BackRestState):
    if not state['spec_data'].get('flame_retardant', False):
        state['validation_errors'].append('Missing flame retardancy certificate.')
        state['approved'] = False
    return state
graph = StateGraph(BackRestState)
graph.add_node('validate_ergonomics', validate_ergonomic_specs)
graph.add_node('compliance_review', safety_compliance_check)
graph.set_entry_point('validate_ergonomics')
graph.add_edge('validate_ergonomics', 'compliance_review')
graph.add_edge('compliance_review', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'approved': False,
    'validation_errors': []
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
