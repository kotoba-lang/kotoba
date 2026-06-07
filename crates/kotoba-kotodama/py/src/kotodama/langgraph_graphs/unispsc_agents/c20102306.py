from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class RobotServoState(TypedDict):
    part_number: str
    torque_requirements: float
    ip_rating: str
    validation_passed: bool
    log: List[str]

def validate_specs(state: RobotServoState) -> RobotServoState:
    passed = state['torque_requirements'] > 0 and state['ip_rating'] in ['IP65', 'IP67']
    state['validation_passed'] = passed
    state['log'].append(f'Validation result: {passed}')
    return state

def check_certification(state: RobotServoState) -> RobotServoState:
    if state['validation_passed']:
        state['log'].append('Checking compliance with IEC 60034 standards')
    return state

def route_after_validation(state: RobotServoState) -> str:
    return 'check' if state['validation_passed'] else END

graph = StateGraph(RobotServoState)
graph.add_node('validate', validate_specs)
graph.add_node('check', check_certification)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_after_validation)
graph.add_edge('check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'torque_requirements': 0.0,
    'ip_rating': "",
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
