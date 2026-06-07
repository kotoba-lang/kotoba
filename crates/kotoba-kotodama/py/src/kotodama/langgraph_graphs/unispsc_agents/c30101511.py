from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BronzeSpecState(TypedDict):
    material_grade: str
    dimensions: dict
    approved: bool
    validation_log: List[str]

def validate_alloy(state: BronzeSpecState):
    grade = state.get('material_grade')
    if grade in ['C93200', 'C95400']:
        return {'validation_log': ['Alloy Grade Validated']}
    return {'validation_log': ['Invalid Alloy Grade Rejected']}

def check_dimensions(state: BronzeSpecState):
    if all(v > 0 for v in state['dimensions'].values()):
        return {'approved': True}
    return {'approved': False}

graph = StateGraph(BronzeSpecState)
graph.add_node('validate_alloy', validate_alloy)
graph.add_node('check_dimensions', check_dimensions)
graph.set_entry_point('validate_alloy')
graph.add_edge('validate_alloy', 'check_dimensions')
graph.add_edge('check_dimensions', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_grade': "",
    'dimensions': {},
    'approved': False,
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
