from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SteelCanState(TypedDict):
    capacity_liters: float
    material_grade: str
    is_airtight: bool
    validation_errors: List[str]

def validate_spec(state: SteelCanState) -> SteelCanState:
    errors = []
    if state['capacity_liters'] <= 0:
        errors.append('Invalid capacity')
    if not state['is_airtight']:
        errors.append('Airtight seal required for steel cans')
    return {**state, 'validation_errors': errors}

def route_by_validation(state: SteelCanState) -> str:
    return 'END' if not state['validation_errors'] else 'END'

graph = StateGraph(SteelCanState)
graph.add_node('validate', validate_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'capacity_liters': 0.0,
    'material_grade': "",
    'is_airtight': False,
    'validation_errors': []
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
