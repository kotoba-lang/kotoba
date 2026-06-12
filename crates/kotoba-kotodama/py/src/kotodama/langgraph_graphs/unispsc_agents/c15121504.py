from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ResinState(TypedDict):
    material_id: str
    spec_requirements: dict
    validation_logs: List[str]
    is_approved: bool

def validate_resin_specs(state: ResinState) -> ResinState:
    mfi = state['spec_requirements'].get('mfi', 0)
    if mfi < 10 or mfi > 50:
        state['validation_logs'].append('MFI outside acceptable range for manufacturing.')
        state['is_approved'] = False
    else:
        state['validation_logs'].append('MFI validation passed.')
    return state

def check_compliance(state: ResinState) -> ResinState:
    if 'rohs_certified' in state['spec_requirements']:
        state['validation_logs'].append('Compliance checked.')
    else:
        state['is_approved'] = False
        state['validation_logs'].append('Missing compliance documentation.')
    return state

graph = StateGraph(ResinState)
graph.add_node('validate', validate_resin_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'spec_requirements': {},
    'validation_logs': [],
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
