from typing import TypedDict
from langgraph.graph import StateGraph, END

class FilterHousingState(TypedDict):
    spec_sheet: dict
    validation_results: dict

def validate_pressure_compliance(state: FilterHousingState):
    pressure = state['spec_sheet'].get('max_pressure')
    state['validation_results'] = {'pressure_ok': pressure > 0}
    return state

def check_material_safety(state: FilterHousingState):
    material = state['spec_sheet'].get('material')
    state['validation_results']['material_compatible'] = material in ['SS316', 'Carbon Steel', 'Polypropylene']
    return state

graph = StateGraph(FilterHousingState)
graph.add_node("validate_pressure", validate_pressure_compliance)
graph.add_node("check_material", check_material_safety)
graph.set_entry_point("validate_pressure")
graph.add_edge("validate_pressure", "check_material")
graph.add_edge("check_material", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_sheet': {},
    'validation_results': {}
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
