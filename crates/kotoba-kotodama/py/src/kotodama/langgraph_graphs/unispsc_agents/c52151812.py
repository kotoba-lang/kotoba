from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class KitchenwareState(TypedDict):
    item_name: str
    specs: dict
    is_compliant: bool

def validate_food_grade(state: KitchenwareState):
    state['is_compliant'] = 'food_grade_cert' in state['specs']
    return state

def check_thermal_specs(state: KitchenwareState):
    if state['is_compliant']:
        state['is_compliant'] = 'material_grade' in state['specs']
    return state

graph = StateGraph(KitchenwareState)
graph.add_node('validate_food_grade', validate_food_grade)
graph.add_node('check_thermal_specs', check_thermal_specs)
graph.add_edge('validate_food_grade', 'check_thermal_specs')
graph.add_edge('check_thermal_specs', END)
graph.set_entry_point('validate_food_grade')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'item_name': "",
    'specs': {},
    'is_compliant': False
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
