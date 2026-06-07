from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class LivestockState(TypedDict):
    livestock_ids: List[str]
    health_status: List[str]
    validation_results: Annotated[List[str], operator.add]

def validate_health(state: LivestockState):
    results = [f'Validated {id}' for id in state['livestock_ids']]
    return {'validation_results': results}

def check_quarantine(state: LivestockState):
    return {'validation_results': ['Quarantine clearance successful']}

graph = StateGraph(LivestockState)
graph.add_node('health_check', validate_health)
graph.add_node('quarantine_check', check_quarantine)
graph.set_entry_point('health_check')
graph.add_edge('health_check', 'quarantine_check')
graph.add_edge('quarantine_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'livestock_ids': [],
    'health_status': [],
    'validation_results': []
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
