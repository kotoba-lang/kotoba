from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class LubricantState(TypedDict):
    commodity_code: str
    spec_data: dict
    validation_checks: List[str]
    is_approved: bool

def validate_viscosity(state: LubricantState) -> LubricantState:
    if 'viscosity_grade' in state['spec_data']:
        state['validation_checks'].append('Viscosity valid')
    return state

def check_compliance(state: LubricantState) -> LubricantState:
    if 'iso_standard_compliance' in state['spec_data']:
        state['validation_checks'].append('ISO compliant')
        state['is_approved'] = True
    return state

graph = StateGraph(LubricantState)
graph.add_node('validate_viscosity', validate_viscosity)
graph.add_node('check_compliance', check_compliance)
graph.add_edge('validate_viscosity', 'check_compliance')
graph.add_edge('check_compliance', END)
graph.set_entry_point('validate_viscosity')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'spec_data': {},
    'validation_checks': [],
    'is_approved': False
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
