from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    tube_specs: dict
    compliance_check: bool

def validate_biocompatibility(state: ProcurementState):
    # Logic to verify ISO 10993 documentation
    state['compliance_check'] = 'material_iso10993' in state['tube_specs']
    return state

def check_dimensions(state: ProcurementState):
    # Validate French gauge sizing
    state['compliance_check'] = state['tube_specs'].get('french_size', 0) > 0
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate_material', validate_biocompatibility)
graph.add_node('check_size', check_dimensions)
graph.add_edge('validate_material', 'check_size')
graph.add_edge('check_size', END)
graph.set_entry_point('validate_material')

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'tube_specs': {},
    'compliance_check': False
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
