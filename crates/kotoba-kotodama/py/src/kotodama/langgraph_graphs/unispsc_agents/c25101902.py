from typing import TypedDict
from langgraph.graph import StateGraph, END

class MotorHomeState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_specs(state: MotorHomeState):
    # Check for required safety and emission specs
    required = ['chassis_model', 'engine_emissions_rating']
    state['is_compliant'] = all(k in state['spec_data'] for k in required)
    return state

def check_compliance(state: MotorHomeState):
    return 'compliant_node' if state['is_compliant'] else 'reject_node'

graph = StateGraph(MotorHomeState)
graph.add_node('validation', validate_specs)
graph.add_node('compliant_node', lambda s: s)
graph.add_node('reject_node', lambda s: s)
graph.set_entry_point('validation')
graph.add_conditional_edges('validation', check_compliance)
graph.add_edge('compliant_node', END)
graph.add_edge('reject_node', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
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
