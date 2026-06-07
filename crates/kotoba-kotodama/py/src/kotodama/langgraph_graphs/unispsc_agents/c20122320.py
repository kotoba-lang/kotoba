from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class RobotState(TypedDict):
    task_id: str
    arm_id: str
    payload: float
    status: str
    logs: Annotated[List[str], operator.add]

def validate_payload(state: RobotState):
    if state['payload'] > 50.0:
        return {'status': 'error', 'logs': ['Payload exceeds safety limit for this arm model']}
    return {'status': 'validated', 'logs': ['Payload within safe operational parameters']}

def execute_motion_plan(state: RobotState):
    if state['status'] == 'validated':
        return {'status': 'executing', 'logs': ['Motion trajectory generated and uploaded to controller']}
    return {'status': 'aborted', 'logs': ['Motion execution cancelled due to invalid state']}

graph = StateGraph(RobotState)
graph.add_node('validate', validate_payload)
graph.add_node('execute', execute_motion_plan)
graph.set_entry_point('validate')
graph.add_edge('validate', 'execute')
graph.add_edge('execute', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'task_id': "",
    'arm_id': "",
    'payload': 0.0,
    'status': "",
    'logs': []
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
