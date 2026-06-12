from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class CarbonFiberState(TypedDict):
    material_id: str
    spec_data: Dict[str, Any]
    validation_log: List[str]
    export_compliant: bool

def validate_specs(state: CarbonFiberState) -> CarbonFiberState:
    spec = state.get('spec_data', {})
    logs = state.get('validation_log', [])
    if spec.get('tensile_strength_mpa', 0) < 3000:
        logs.append('Validation Error: Insufficient tensile strength')
    state['validation_log'] = logs
    return state

def check_export_control(state: CarbonFiberState) -> CarbonFiberState:
    # High-performance carbon fiber is often dual-use
    state['export_compliant'] = state['spec_data'].get('elastic_modulus_gpa', 0) < 230
    return state

builder = StateGraph(CarbonFiberState)
builder.add_node('validate', validate_specs)
builder.add_node('export_check', check_export_control)
builder.set_entry_point('validate')
builder.add_edge('validate', 'export_check')
builder.add_edge('export_check', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'spec_data': {},
    'validation_log': [],
    'export_compliant': False
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
