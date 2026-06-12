from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class RobotHoldingState(TypedDict):
    part_id: str
    spec_data: dict
    validation_logs: Annotated[list[str], operator.add]
    is_approved: bool

def validate_clamping_specs(state: RobotHoldingState):
    specs = state['spec_data']
    logs = []
    if specs.get('clamping_force_kn', 0) <= 0:
        logs.append('Invalid clamping force detected.')
    return {'validation_logs': logs, 'is_approved': len(logs) == 0}

def structural_integrity_check(state: RobotHoldingState):
    logs = ['Checking material hardness and load capacity...']
    return {'validation_logs': logs}

builder = StateGraph(RobotHoldingState)
builder.add_node('validate', validate_clamping_specs)
builder.add_node('integrity_check', structural_integrity_check)
builder.set_entry_point('validate')
builder.add_edge('validate', 'integrity_check')
builder.add_edge('integrity_check', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'spec_data': {},
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
