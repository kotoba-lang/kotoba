from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ActuatorState(TypedDict):
    spec_data: dict
    validation_results: List[str]
    is_compliant: bool

def validate_specs(state: ActuatorState) -> ActuatorState:
    specs = state['spec_data']
    results = []
    if specs.get('rated_torque_nm', 0) <= 0:
        results.append('Invalid torque value')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

def route_by_compliance(state: ActuatorState) -> str:
    return 'process' if state['is_compliant'] else 'flag_error'

graph = StateGraph(ActuatorState)
graph.add_node('validate', validate_specs)
graph.add_node('process', lambda s: s)
graph.add_node('flag_error', lambda s: s)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance)
graph.add_edge('process', END)
graph.add_edge('flag_error', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_results': [],
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
