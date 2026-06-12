from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BusStationState(TypedDict):
    location: str
    specifications: dict
    is_compliant: bool

def validate_infrastructure(state: BusStationState):
    # Simulate building code and ADA compliance logic
    specs = state.get('specifications', {})
    compliant = specs.get('ada_compliant', False) and specs.get('wind_rating', 0) > 100
    return {'is_compliant': compliant}

def architect_review(state: BusStationState):
    print(f'Conducting structural review for: {state["location"]}')
    return {}

graph = StateGraph(BusStationState)
graph.add_node('validate', validate_infrastructure)
graph.add_node('review', architect_review)
graph.set_entry_point('validate')
graph.add_edge('validate', 'review')
graph.add_edge('review', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'location': "",
    'specifications': {},
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
