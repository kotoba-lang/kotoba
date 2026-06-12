from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PetroState(TypedDict):
    batch_id: str
    composition_data: dict
    validation_checks: List[str]
    approved: bool

def validate_composition(state: PetroState):
    checks = []
    if state['composition_data'].get('sulfur', 0) < 0.5:
        checks.append('sulfur_limit_pass')
    return {'validation_checks': checks}

def safety_routing(state: PetroState):
    if 'sulfur_limit_pass' in state['validation_checks']:
        return 'approve'
    return 'reject'

graph = StateGraph(PetroState)
graph.add_node('validate', validate_composition)
graph.add_edge('validate', 'approve')
graph.add_node('approve', lambda s: {'approved': True})
graph.set_entry_point('validate')
graph.add_edge('approve', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'composition_data': {},
    'validation_checks': [],
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
