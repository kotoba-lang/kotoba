from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class CleaningSpecs(TypedDict):
    material_type: str
    compliance_codes: List[str]
    is_verified: bool

def validate_cleaning_standards(state: CleaningSpecs):
    required = ['ISO_15883', 'FDA_CLEARED']
    state['is_verified'] = all(code in state['compliance_codes'] for code in required)
    return state

def check_material_safety(state: CleaningSpecs):
    if state['material_type'] == 'aluminium' and 'corrosion_inhibitor' not in state.get('compliance_codes', []):
        state['is_verified'] = False
    return state

graph = StateGraph(CleaningSpecs)
graph.add_node('validate', validate_cleaning_standards)
graph.add_node('safety_check', check_material_safety)
graph.add_edge('validate', 'safety_check')
graph.add_edge('safety_check', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_type': "",
    'compliance_codes': [],
    'is_verified': False
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
