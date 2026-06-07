from typing import TypedDict
from langgraph.graph import StateGraph, END

class StructureState(TypedDict):
    spec_data: dict
    validation_results: dict

def validate_structural_specs(state: StructureState):
    # Simulate CAD/Engineering verification logic
    compliance = 'pass' if 'wind_load_capacity' in state['spec_data'] else 'fail'
    return {'validation_results': {'structural_integrity': compliance}}

def check_delivery_logistics(state: StructureState):
    # Simulate site accessibility and transport feasibility check
    return {'validation_results': {'logistics': 'verified'}}

graph = StateGraph(StructureState)
graph.add_node('structural_validation', validate_structural_specs)
graph.add_node('logistics_check', check_delivery_logistics)
graph.set_entry_point('structural_validation')
graph.add_edge('structural_validation', 'logistics_check')
graph.add_edge('logistics_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
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
