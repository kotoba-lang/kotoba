from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class RobotBearingState(TypedDict):
    part_number: str
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_bearing_specs(state: RobotBearingState):
    specs = state['spec_data']
    errors = []
    if specs.get('rotational_accuracy_class', 0) < 5:
        errors.append('Precision class below industrial standard')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def route_to_qa(state: RobotBearingState):
    return 'QA_NODE' if state['validation_passed'] else 'REJECT_NODE'

graph = StateGraph(RobotBearingState)
graph.add_node('VALIDATE', validate_bearing_specs)
graph.add_node('QA_NODE', lambda s: {'validation_passed': True})
graph.add_node('REJECT_NODE', lambda s: {'validation_passed': False})
graph.set_entry_point('VALIDATE')
graph.add_conditional_edges('VALIDATE', route_to_qa)
graph.add_edge('QA_NODE', END)
graph.add_edge('REJECT_NODE', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'spec_data': {},
    'validation_passed': False,
    'error_log': []
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
