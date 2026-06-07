from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CoastguardProjectState(TypedDict):
    project_id: str
    security_clearance: bool
    structural_specs: List[str]
    approved: bool

def validate_clearance(state: CoastguardProjectState):
    state['security_clearance'] = True
    return state

def validate_specs(state: CoastguardProjectState):
    state['approved'] = len(state['structural_specs']) > 0
    return state

graph = StateGraph(CoastguardProjectState)
graph.add_node('clearance_check', validate_clearance)
graph.add_node('spec_validation', validate_specs)
graph.set_entry_point('clearance_check')
graph.add_edge('clearance_check', 'spec_validation')
graph.add_edge('spec_validation', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'project_id': "",
    'security_clearance': False,
    'structural_specs': [],
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
