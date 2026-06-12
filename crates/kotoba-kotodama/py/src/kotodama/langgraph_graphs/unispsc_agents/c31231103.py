from typing import TypedDict
from langgraph.graph import StateGraph, END

class BrassStockState(TypedDict):
    alloy_grade: str
    dimensions: dict
    compliance_verified: bool

def validate_material_grade(state: BrassStockState):
    valid_grades = ['C360', 'C385', 'C464']
    state['compliance_verified'] = state['alloy_grade'] in valid_grades
    return state

def check_dimensions(state: BrassStockState):
    if state['dimensions'].get('diameter', 0) <= 0:
        state['compliance_verified'] = False
    return state

graph = StateGraph(BrassStockState)
graph.add_node('validate_grade', validate_material_grade)
graph.add_node('check_dims', check_dimensions)
graph.set_entry_point('validate_grade')
graph.add_edge('validate_grade', 'check_dims')
graph.add_edge('check_dims', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'alloy_grade': "",
    'dimensions': {},
    'compliance_verified': False
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
