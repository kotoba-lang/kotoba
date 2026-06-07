from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MaterialHandlingState(TypedDict):
    equipment_type: str
    specifications: dict
    is_validated: bool
    compliance_report: str

def validate_specs(state: MaterialHandlingState):
    print('Validating engineering specs for material handling equipment...')
    state['is_validated'] = all(k in state['specifications'] for k in ['load_capacity', 'safety_standard'])
    return state

def generate_compliance_report(state: MaterialHandlingState):
    if state['is_validated']:
        state['compliance_report'] = 'Equipment meets safety and structural standards.'
    else:
        state['compliance_report'] = 'Failed validation: Missing critical safety specs.'
    return state

graph = StateGraph(MaterialHandlingState)
graph.add_node('validate', validate_specs)
graph.add_node('report', generate_compliance_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'equipment_type': "",
    'specifications': {},
    'is_validated': False,
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
