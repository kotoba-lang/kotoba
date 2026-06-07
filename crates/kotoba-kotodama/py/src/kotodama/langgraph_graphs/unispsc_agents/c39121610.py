from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SurgeState(TypedDict):
    specs: dict
    is_compliant: bool
    validation_log: List[str]

def validate_specs(state: SurgeState):
    log = []
    compliant = True
    required = ['voltage', 'surge_rating', 'standards']
    for field in required:
        if field not in state['specs']:
            compliant = False
            log.append(f'Missing field: {field}')
    return {'is_compliant': compliant, 'validation_log': log}

def route_by_compliance(state: SurgeState):
    return 'compliant_node' if state['is_compliant'] else 'reject_node'

graph = StateGraph(SurgeState)
graph.add_node('validate', validate_specs)
graph.add_node('compliant_node', lambda s: s)
graph.add_node('reject_node', lambda s: s)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance)
graph.add_edge('compliant_node', END)
graph.add_edge('reject_node', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'is_compliant': False,
    'validation_log': []
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
