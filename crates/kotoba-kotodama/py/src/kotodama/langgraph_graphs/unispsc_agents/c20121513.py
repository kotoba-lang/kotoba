from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    payload: float
    precision: float
    workflow_steps: List[str]
    validation_status: str

def validate_specs(state: RobotState):
    status = 'PASS' if state['payload'] > 0 and state['precision'] < 0.1 else 'FAIL'
    return {'validation_status': status}

def plan_tasks(state: RobotState):
    return {'workflow_steps': ['Initialize', 'Calibrate', 'Run Cycle', 'Safety Check']}

graph = StateGraph(RobotState)
graph.add_node('validate', validate_specs)
graph.add_node('plan', plan_tasks)
graph.add_edge('validate', 'plan')
graph.add_edge('plan', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'payload': 0.0,
    'precision': 0.0,
    'workflow_steps': [],
    'validation_status': ""
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
