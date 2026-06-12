from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class OvershoeState(TypedDict):
    material_type: str
    iso_rating: str
    compliance_ok: bool

def validate_materials(state: OvershoeState):
    state['compliance_ok'] = state['material_type'] in ['Latex', 'PE', 'CPE']
    return state

def check_iso_standards(state: OvershoeState):
    if state['compliance_ok']:
        state['compliance_ok'] = 'ISO' in state['iso_rating']
    return state

graph = StateGraph(OvershoeState)
graph.add_node('material_check', validate_materials)
graph.add_node('iso_check', check_iso_standards)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'iso_check')
graph.add_edge('iso_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_type': "",
    'iso_rating': "",
    'compliance_ok': False
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
