from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class RobotAttachmentState(TypedDict):
    spec_data: dict
    validation_results: list
    is_approved: bool

def validate_payload_specs(state: RobotAttachmentState):
    spec = state['spec_data']
    payload = spec.get('payload_capacity_kg', 0)
    valid = 0 < payload < 500
    return {'validation_results': [f'Payload {payload}kg valid: {valid}'], 'is_approved': valid}

def check_compliance(state: RobotAttachmentState):
    spec = state['spec_data']
    compliant = 'ISO' in spec.get('safety_standard_compliance', '')
    return {'validation_results': state['validation_results'] + [f'ISO compliant: {compliant}'], 'is_approved': state['is_approved'] and compliant}

graph = StateGraph(RobotAttachmentState)
graph.add_node('validate_payload', validate_payload_specs)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('validate_payload')
graph.add_edge('validate_payload', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
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
