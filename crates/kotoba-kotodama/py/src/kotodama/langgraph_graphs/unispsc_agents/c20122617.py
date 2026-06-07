from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotComponentState(TypedDict):
    component_id: str
    spec_requirements: dict
    validation_log: List[str]
    approved: bool

def validate_specs(state: RobotComponentState) -> RobotComponentState:
    # Simulate CAD/Tolerance validation logic
    tolerance = state['spec_requirements'].get('precision_tolerance_mm', 1.0)
    if tolerance <= 0.05:
        state['validation_log'].append('High precision validation passed.')
        state['approved'] = True
    else:
        state['validation_log'].append('Tolerance out of range.')
        state['approved'] = False
    return state

def check_compliance(state: RobotComponentState) -> RobotComponentState:
    # Simulate dual-use export control check
    if state.get('approved'):
        state['validation_log'].append('Compliance review cleared.')
    return state

graph = StateGraph(RobotComponentState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'component_id': "",
    'spec_requirements': {},
    'validation_log': [],
    'approved': False
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
