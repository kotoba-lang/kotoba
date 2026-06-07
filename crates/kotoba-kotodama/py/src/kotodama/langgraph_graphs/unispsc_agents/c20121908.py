from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ActuatorState(TypedDict):
    spec_requirements: dict
    validation_results: Annotated[list[str], operator.add]
    is_approved: bool

def validate_torque_specs(state: ActuatorState) -> ActuatorState:
    torque = state['spec_requirements'].get('torque_rating_nm', 0)
    if torque < 0.5:
        state['validation_results'].append('Torque below industrial baseline.')
        state['is_approved'] = False
    return state

def check_compliance(state: ActuatorState) -> ActuatorState:
    if 'certification_iso' not in state['spec_requirements']:
        state['validation_results'].append('Missing ISO certification.')
        state['is_approved'] = False
    return state

builder = StateGraph(ActuatorState)
builder.add_node('torque_check', validate_torque_specs)
builder.add_node('compliance_check', check_compliance)
builder.add_edge('torque_check', 'compliance_check')
builder.add_edge('compliance_check', END)
builder.set_entry_point('torque_check')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_requirements': {},
    'validation_results': [],
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
