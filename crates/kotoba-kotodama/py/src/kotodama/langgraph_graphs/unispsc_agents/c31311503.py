from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PipeAssemblyState(TypedDict):
    specs: dict
    validation_results: List[str]
    is_compliant: bool

def validate_material(state: PipeAssemblyState):
    is_alloy_x = state['specs'].get('alloy_type') == 'Hastelloy X'
    return {'validation_results': ['Material check passed'] if is_alloy_x else ['Invalid Alloy Error']}

def conduct_nd_testing(state: PipeAssemblyState):
    is_passed = state['specs'].get('rt_score', 0) > 95
    return {'validation_results': state['validation_results'] + ['NDT Passed'] if is_passed else ['NDT Failed']}

graph = StateGraph(PipeAssemblyState)
graph.add_node('validate_material', validate_material)
graph.add_node('conduct_ndt', conduct_nd_testing)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'conduct_ndt')
graph.add_edge('conduct_ndt', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
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
