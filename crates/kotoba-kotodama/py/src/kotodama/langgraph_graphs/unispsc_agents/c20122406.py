from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotBearingState(TypedDict):
    part_id: str
    specs: dict
    validation_passed: bool
    log: List[str]

def validate_bearing(state: RobotBearingState) -> RobotBearingState:
    specs = state.get('specs', {})
    load = specs.get('load_capacity_kn', 0)
    if load > 0:
        state['validation_passed'] = True
        state['log'].append('Validation successful: Load capacity within safety limits.')
    else:
        state['validation_passed'] = False
        state['log'].append('Validation failed: Missing or invalid load capacity.')
    return state

def route_by_validation(state: RobotBearingState) -> str:
    return 'process' if state['validation_passed'] else END

def process_bearing_workflow(state: RobotBearingState) -> RobotBearingState:
    state['log'].append('Processing robotic bearing assembly workflow...')
    return state

graph = StateGraph(RobotBearingState)
graph.add_node('validate', validate_bearing)
graph.add_node('process', process_bearing_workflow)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'specs': {},
    'validation_passed': False,
    'log': []
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
