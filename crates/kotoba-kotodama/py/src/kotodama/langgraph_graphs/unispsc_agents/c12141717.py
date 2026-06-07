from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    catalyst_id: str
    purity_level: float
    safety_clearance: bool
    process_steps: list[str]

def validate_composition(state: CatalystState):
    # Simulate high-precision chemical composition validation
    if state['purity_level'] >= 0.99:
        return {'safety_clearance': True}
    return {'safety_clearance': False}

def route_by_safety(state: CatalystState):
    return 'process' if state['safety_clearance'] else 'flag_hazard'

def run_industrial_prep(state: CatalystState):
    return {'process_steps': ['standardized_mixing', 'catalytic_activation_check']}

graph = StateGraph(CatalystState)
graph.add_node('validate', validate_composition)
graph.add_node('process', run_industrial_prep)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_safety, {'process': 'process', 'flag_hazard': END})
graph.add_edge('process', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'catalyst_id': "",
    'purity_level': 0.0,
    'safety_clearance': False,
    'process_steps': []
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
