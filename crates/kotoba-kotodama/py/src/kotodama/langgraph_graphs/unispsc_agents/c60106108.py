from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class HazardState(TypedDict):
    materials: List[str]
    compliance_docs: List[str]
    hazard_level: str
    approved: bool

def validate_materials(state: HazardState):
    # Simulate safety check for hazardous teaching materials
    hazard_check = all('SDS' in doc for doc in state['compliance_docs'])
    return {'approved': hazard_check}

def safety_routing(state: HazardState):
    return 'process' if state['approved'] else END

graph_builder = StateGraph(HazardState)
graph_builder.add_node('safety_check', validate_materials)
graph_builder.set_entry_point('safety_check')
graph_builder.add_edge('safety_check', END)
graph = graph_builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'materials': [],
    'compliance_docs': [],
    'hazard_level': "",
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
