from typing import TypedDict
from langgraph.graph import StateGraph, END

class AlloyState(TypedDict):
    material_spec: dict
    compliance_report: str
    approved: bool

def validate_composition(state: AlloyState):
    # Simulate CAD/Spec verification logic
    is_valid = state['material_spec'].get('purity') > 99.5
    return {'compliance_report': 'Passed' if is_valid else 'Failed', 'approved': is_valid}

def process_export_check(state: AlloyState):
    # Dual-use export control routing
    return {'compliance_report': state['compliance_report'] + ' - Export Review Cleared'}

graph = StateGraph(AlloyState)
graph.add_node('validation', validate_composition)
graph.add_node('export_check', process_export_check)
graph.set_entry_point('validation')
graph.add_edge('validation', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_spec': {},
    'compliance_report': "",
    'approved': False
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
