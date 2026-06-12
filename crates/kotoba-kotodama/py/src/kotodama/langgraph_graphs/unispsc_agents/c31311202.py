import operator
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PipeState(TypedDict):
    spec_data: dict
    validation_log: Annotated[List[str], operator.add]
    is_approved: bool

def validate_material(state: PipeState):
    grade = state['spec_data'].get('material_grade')
    status = 'Pass' if grade in ['A36', 'A53'] else 'Fail: Incompatible Steel Grade'
    return {'validation_log': [f'Material validation: {status}']}

def check_pressure_specs(state: PipeState):
    rating = state['spec_data'].get('pressure_rating', 0)
    status = 'Compliance' if rating > 0 else 'Error: Invalid Pressure Rating'
    return {'validation_log': [f'Pressure criteria: {status}']}

graph = StateGraph(PipeState)
graph.add_node('material_check', validate_material)
graph.add_node('pressure_check', check_pressure_specs)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'pressure_check')
graph.add_edge('pressure_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_log': [],
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
