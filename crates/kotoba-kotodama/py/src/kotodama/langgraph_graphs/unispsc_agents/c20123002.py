from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class RobotEndEffectorState(TypedDict):
    commodity_code: str
    specifications: dict
    validation_results: Annotated[Sequence[str], operator.add]
    status: str

def validate_payload(state: RobotEndEffectorState):
    payload = state['specifications'].get('payload_capacity_kg', 0)
    if payload > 0:
        return {'validation_results': ['Payload within operational limits']}
    return {'validation_results': ['Payload validation failed']}

def check_compatibility(state: RobotEndEffectorState):
    compat = state['specifications'].get('compatibility_iso_standard', '')
    if 'ISO' in compat:
        return {'validation_results': ['ISO compatibility verified']}
    return {'validation_results': ['Compatibility standard missing']}

def finalize_process(state: RobotEndEffectorState):
    return {'status': 'READY_FOR_INTEGRATION'}

graph = StateGraph(RobotEndEffectorState)
graph.add_node('validate_payload', validate_payload)
graph.add_node('check_compatibility', check_compatibility)
graph.add_node('finalize', finalize_process)
graph.set_entry_point('validate_payload')
graph.add_edge('validate_payload', 'check_compatibility')
graph.add_edge('check_compatibility', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'specifications': {},
    'validation_results': [],
    'status': ""
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
