from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    spec: dict
    validation_errors: List[str]
    is_compliant: bool

def validate_robot_specs(state: RobotState):
    spec = state['spec']
    errors = []
    if spec.get('payload_capacity_kg', 0) <= 0:
        errors.append('Invalid payload capacity')
    if not spec.get('safety_certification_iso10218', False):
        errors.append('Missing mandatory ISO10218 certification')
    return {'validation_errors': errors, 'is_compliant': len(errors) == 0}

def route_procurement(state: RobotState):
    return 'compliant' if state['is_compliant'] else 'reject'

graph = StateGraph(RobotState)
graph.add_node('validator', validate_robot_specs)
graph.set_entry_point('validator')
graph.add_conditional_edges('validator', route_procurement, {'compliant': END, 'reject': END})

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec': {},
    'validation_errors': [],
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
