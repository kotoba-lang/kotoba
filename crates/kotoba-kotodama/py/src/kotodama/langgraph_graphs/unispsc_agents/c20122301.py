from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class RobotHandState(TypedDict):
    payload: float
    gripper_config: dict
    validation_results: list[str]

def validate_payload(state: RobotHandState):
    limit = 5.0
    if state['payload'] > limit:
        return {'validation_results': ['Payload exceeds safety limit for this class']}
    return {'validation_results': ['Payload valid']}

def configure_gripper(state: RobotHandState):
    # Simulate hardware interface configuration
    return {'validation_results': state['validation_results'] + ['Interface protocol configured']}

graph = StateGraph(RobotHandState)
graph.add_node('validate', validate_payload)
graph.add_node('configure', configure_gripper)
graph.set_entry_point('validate')
graph.add_edge('validate', 'configure')
graph.add_edge('configure', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'payload': 0.0,
    'gripper_config': {},
    'validation_results': []
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
