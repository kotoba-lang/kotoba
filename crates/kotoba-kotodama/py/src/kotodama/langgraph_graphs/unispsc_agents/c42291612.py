from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalRongeurState(TypedDict):
    spec_sheet: dict
    validation_status: bool
    compliance_report: str

def validate_medical_grade(state: SurgicalRongeurState):
    material = state['spec_sheet'].get('material', '')
    is_valid = material == 'Surgical Stainless Steel'
    return {'validation_status': is_valid, 'compliance_report': 'Material check passed' if is_valid else 'Invalid material'}

def process_sterilization_flow(state: SurgicalRongeurState):
    if state['validation_status']:
        return {'compliance_report': 'Ready for sterilization validation'}
    return {'compliance_report': 'Rejected due to material non-compliance'}

graph = StateGraph(SurgicalRongeurState)
graph.add_node('validate', validate_medical_grade)
graph.add_node('sterilize', process_sterilization_flow)
graph.add_edge('validate', 'sterilize')
graph.add_edge('sterilize', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_sheet': {},
    'validation_status': False,
    'compliance_report': ""
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
