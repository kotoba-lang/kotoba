from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, END

class LivestockState(TypedDict):
    animal_id: str
    health_status: str
    quarantine_clearance: bool
    history: List[str]

def validate_health(state: LivestockState):
    # Simulate health verification check
    return {'health_status': 'verified' if state['health_status'] == 'healthy' else 'rejected'}

def check_quarantine(state: LivestockState):
    # Simulate quarantine logic
    return {'quarantine_clearance': True}

graph = StateGraph(LivestockState)
graph.add_node('health', validate_health)
graph.add_node('quarantine', check_quarantine)
graph.set_entry_point('health')
graph.add_edge('health', 'quarantine')
graph.add_edge('quarantine', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'animal_id': "",
    'health_status': "",
    'quarantine_clearance': False,
    'history': []
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
