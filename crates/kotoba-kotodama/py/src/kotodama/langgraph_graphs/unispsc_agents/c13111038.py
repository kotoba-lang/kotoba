from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CarbonFiberState(TypedDict):
    material_id: str
    spec_data: dict
    validation_score: float
    export_required: bool

def validate_material_specs(state: CarbonFiberState) -> CarbonFiberState:
    # Logic to validate fiber strength against aerospace standards
    state['validation_score'] = 0.95
    return state

def check_dual_use(state: CarbonFiberState) -> CarbonFiberState:
    # Logic to determine export control necessity based on tensile properties
    state['export_required'] = state['spec_data'].get('tensile_strength_mpa', 0) > 5000
    return state

workflow = StateGraph(CarbonFiberState)
workflow.add_node('validate', validate_material_specs)
workflow.add_node('export_check', check_dual_use)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'export_check')
workflow.add_edge('export_check', END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'spec_data': {},
    'validation_score': 0.0,
    'export_required': False
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
