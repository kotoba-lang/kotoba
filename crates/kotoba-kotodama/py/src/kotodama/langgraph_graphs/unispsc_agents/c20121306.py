from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class RobotEndEffectorState(TypedDict):
    spec_requirements: dict
    validation_results: Annotated[list, operator.add]
    is_approved: bool

def validate_payload(state: RobotEndEffectorState):
    payload = state['spec_requirements'].get('payload_capacity_kg', 0)
    result = "Payload validation passed" if payload > 0 else "Payload validation failed"
    return {'validation_results': [result]}

def check_safety_compliance(state: RobotEndEffectorState):
    compliant = state['spec_requirements'].get('iso_compliance_cert', False)
    result = "Safety compliance verified" if compliant else "Safety compliance missing"
    return {'validation_results': [result]}

builder = StateGraph(RobotEndEffectorState)
builder.add_node("validate_payload", validate_payload)
builder.add_node("check_safety_compliance", check_safety_compliance)
builder.set_entry_point("validate_payload")
builder.add_edge("validate_payload", "check_safety_compliance")
builder.add_edge("check_safety_compliance", END)
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
