from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class MetalPowderState(TypedDict):
    material_id: str
    analysis_results: Dict[str, Any]
    is_compliant: bool
    validation_log: List[str]

def validate_material_specs(state: MetalPowderState) -> MetalPowderState:
    # Simulate spectroscopic and laser diffraction analysis logic
    results = state.get('analysis_results', {})
    purity = results.get('purity', 0)
    state['is_compliant'] = purity >= 99.9
    state['validation_log'].append(f'Purity check: {purity}% compliant={state["is_compliant"]}')
    return state

def export_control_check(state: MetalPowderState) -> MetalPowderState:
    # Logic for dual-use verification
    state['validation_log'].append('Export control check initiated for high-purity metallic content.')
    return state

def build_metal_procurement_graph():
    graph = StateGraph(MetalPowderState)
    graph.add_node('validate', validate_material_specs)
    graph.add_node('export_check', export_control_check)
    graph.set_entry_point('validate')
    graph.add_edge('validate', 'export_check')
    graph.add_edge('export_check', END)
    return graph.compile()

graph = build_metal_procurement_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'analysis_results': {},
    'is_compliant': False,
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
