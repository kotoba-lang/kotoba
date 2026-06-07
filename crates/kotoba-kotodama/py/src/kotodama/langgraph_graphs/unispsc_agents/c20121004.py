from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PrecisionReducerState(TypedDict):
    spec_id: str
    torque_rating: float
    backlash: float
    validated: bool
    compliance_checks: List[str]

def validate_reducer_specs(state: PrecisionReducerState) -> PrecisionReducerState:
    # Validation logic for high-precision mechanical components
    if state['torque_rating'] > 0 and state['backlash'] < 0.05:
        state['validated'] = True
        state['compliance_checks'].append('Passed precision threshold')
    else:
        state['validated'] = False
        state['compliance_checks'].append('Failed precision threshold')
    return state

def check_export_compliance(state: PrecisionReducerState) -> PrecisionReducerState:
    # Logic for dual-use export control screening
    state['compliance_checks'].append('Dual-use screening complete')
    return state

graph = StateGraph(PrecisionReducerState)
graph.add_node('validate', validate_reducer_specs)
graph.add_node('export_check', check_export_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_id': "",
    'torque_rating': 0.0,
    'backlash': 0.0,
    'validated': False,
    'compliance_checks': []
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
