from typing import TypedDict
from langgraph.graph import StateGraph, END

class SprayProcurementState(TypedDict):
    material_safety_data: dict
    performance_test_results: dict
    is_compliant: bool

def validate_material(state: SprayProcurementState):
    # Simulate material compliance check
    state['is_compliant'] = state['material_safety_data'].get('bpa_free', False)
    return state

def validate_performance(state: SprayProcurementState):
    # Simulate spray mechanism QC
    if state['performance_test_results'].get('leak_rate', 1.0) < 0.05:
        state['is_compliant'] = True
    else:
        state['is_compliant'] = False
    return state

workflow = StateGraph(SprayProcurementState)
workflow.add_node('check_material', validate_material)
workflow.add_node('check_performance', validate_performance)
workflow.add_edge('check_material', 'check_performance')
workflow.add_edge('check_performance', END)
workflow.set_entry_point('check_material')
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_safety_data': {},
    'performance_test_results': {},
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
