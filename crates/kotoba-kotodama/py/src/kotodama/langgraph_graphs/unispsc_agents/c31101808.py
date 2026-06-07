from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    spec_doc: str
    validation_score: float
    nondestructive_test_results: dict

def validate_material(state: CastingState):
    # Simulate material compliance check for Titanium grade
    state['validation_score'] = 1.0 if 'Grade 5' in state['spec_doc'] else 0.0
    return state

def check_ndt_specs(state: CastingState):
    # Simulate NDT verification logic
    state['nondestructive_test_results'] = {'ultrasonic': 'PASS', 'xray': 'PASS'}
    return state

graph = StateGraph(CastingState)
graph.add_node('validate', validate_material)
graph.add_node('ndt_check', check_ndt_specs)
graph.add_edge('validate', 'ndt_check')
graph.add_edge('ndt_check', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_doc': "",
    'validation_score': 0.0,
    'nondestructive_test_results': {}
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
