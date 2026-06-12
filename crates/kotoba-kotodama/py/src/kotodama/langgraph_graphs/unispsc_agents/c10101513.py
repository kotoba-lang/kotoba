from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PoultryState(TypedDict):
    facility_id: str
    health_status: str
    biosecurity_score: float
    tasks: List[str]

def assess_biosecurity(state: PoultryState):
    score = state.get('biosecurity_score', 0.0)
    status = 'Pass' if score >= 85.0 else 'Flagged_For_Audit'
    return {'health_status': status}

def generate_feed_plan(state: PoultryState):
    return {'tasks': state['tasks'] + ['optimize_nutrient_density']}

def build_graph():
    graph = StateGraph(PoultryState)
    graph.add_node('biosecurity_assessment', assess_biosecurity)
    graph.add_node('feed_optimization', generate_feed_plan)
    graph.add_edge('biosecurity_assessment', 'feed_optimization')
    graph.set_entry_point('biosecurity_assessment')
    graph.add_edge('feed_optimization', END)
    return graph.compile()

graph = build_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'facility_id': "",
    'health_status': "",
    'biosecurity_score': 0.0,
    'tasks': []
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
