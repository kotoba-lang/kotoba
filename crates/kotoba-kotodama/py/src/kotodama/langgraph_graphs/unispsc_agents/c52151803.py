from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class KitchenwareState(TypedDict):
    spec_sheet: dict
    validation_errors: List[str]
    is_approved: bool

def validate_materials(state: KitchenwareState):
    # Business logic for checking material safety standards (e.g., FDA/EU food contact compliance)
    if 'material' not in state['spec_sheet']:
        state['validation_errors'].append('Material field missing')
    return state

def check_thermal_compatibility(state: KitchenwareState):
    # Logic to verify if saucepans work with specified stovetops
    if not state['spec_sheet'].get('ih_compatible', False):
        state['validation_errors'].append('Non-induction compatible items marked for premium tier')
    return state

graph = StateGraph(KitchenwareState)
graph.add_node('validate_materials', validate_materials)
graph.add_node('check_thermal', check_thermal_compatibility)
graph.set_entry_point('validate_materials')
graph.add_edge('validate_materials', 'check_thermal')
graph.add_edge('check_thermal', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_sheet': {},
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
