from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PipeState(TypedDict):
    spec_data: dict
    validation_errors: List[str]
    is_approved: bool

def validate_pressure_rating(state: PipeState):
    rating = state['spec_data'].get('pressure_rating', 0)
    if rating < 150:
        state['validation_errors'].append('Pressure rating below minimum threshold.')
    return state

def check_material_compliance(state: PipeState):
    material = state['spec_data'].get('material', '')
    if material not in ['Carbon Steel', 'Stainless Steel 316']:
        state['validation_errors'].append('Non-compliant material grade.')
    return state

graph = StateGraph(PipeState)
graph.add_node('validate_pressure', validate_pressure_rating)
graph.add_node('check_material', check_material_compliance)
graph.set_entry_point('validate_pressure')
graph.add_edge('validate_pressure', 'check_material')
graph.add_edge('check_material', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_errors': [],
    'is_approved': False
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
