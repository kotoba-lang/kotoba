from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class GameProcurementState(TypedDict):
    title: str
    platform: str
    compliance_checks: List[str]
    approved: bool

def validate_platform(state: GameProcurementState):
    state['compliance_checks'].append('Platform validated')
    return {'compliance_checks': state['compliance_checks']}

def check_age_rating(state: GameProcurementState):
    state['compliance_checks'].append('Rating verified')
    return {'compliance_checks': state['compliance_checks']}

def finalize_procurement(state: GameProcurementState):
    state['approved'] = True
    return {'approved': True}

graph = StateGraph(GameProcurementState)
graph.add_node('validate_platform', validate_platform)
graph.add_node('check_age_rating', check_age_rating)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate_platform')
graph.add_edge('validate_platform', 'check_age_rating')
graph.add_edge('check_age_rating', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'title': "",
    'platform': "",
    'compliance_checks': [],
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
