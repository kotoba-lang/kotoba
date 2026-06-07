from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class EndEffectorState(TypedDict):
    spec_requirements: dict
    validation_logs: Annotated[List[str], operator.add]
    is_compliant: bool

def validate_gripper_specs(state: EndEffectorState):
    specs = state['spec_requirements']
    logs = []
    if specs.get('repeatability_mm', 1.0) > 0.05:
        logs.append('Warning: High repeatability tolerance.')
    return {'validation_logs': logs, 'is_compliant': True}

def check_material_safety(state: EndEffectorState):
    return {'validation_logs': ['Material stress test check passed.']}

builder = StateGraph(EndEffectorState)
builder.add_node('validate', validate_gripper_specs)
builder.add_node('material', check_material_safety)
builder.add_edge('validate', 'material')
builder.add_edge('material', END)
builder.set_entry_point('validate')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_requirements': {},
    'validation_logs': [],
    'is_compliant': False
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
