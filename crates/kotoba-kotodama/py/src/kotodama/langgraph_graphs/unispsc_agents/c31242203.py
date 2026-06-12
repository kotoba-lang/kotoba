from typing import TypedDict
from langgraph.graph import StateGraph, END

class DepolarizerState(TypedDict):
    spec_sheet: dict
    validation_results: dict
    needs_export_license: bool

def validate_specs(state: DepolarizerState):
    errors = []
    if state['spec_sheet'].get('Depolarization_Efficiency', 0) < 0.95:
        errors.append('Efficiency below threshold')
    return {'validation_results': {'errors': errors, 'valid': len(errors) == 0}}

def check_dual_use(state: DepolarizerState):
    # Logic for checking high-spec optics against export control thresholds
    is_controlled = state['spec_sheet'].get('Optical_Damage_Threshold', 0) > 10
    return {'needs_export_license': is_controlled}

graph = StateGraph(DepolarizerState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', check_dual_use)
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_sheet': {},
    'validation_results': {},
    'needs_export_license': False
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
