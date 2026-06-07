from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LeadSheetState(TypedDict):
    purity_level: float
    thickness: float
    safety_clearance: bool
    validation_errors: List[str]

def validate_lead_specs(state: LeadSheetState):
    errors = []
    if state['purity_level'] < 99.9:
        errors.append('Purity below industrial threshold')
    if state['thickness'] <= 0:
        errors.append('Invalid thickness specification')
    return {'validation_errors': errors}

def check_safety_protocols(state: LeadSheetState):
    status = state.get('safety_clearance', False)
    return {'safety_clearance': status}

workflow = StateGraph(LeadSheetState)
workflow.add_node('validate', validate_lead_specs)
workflow.add_node('safety', check_safety_protocols)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'safety')
workflow.add_edge('safety', END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'thickness': 0.0,
    'safety_clearance': False,
    'validation_errors': []
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
