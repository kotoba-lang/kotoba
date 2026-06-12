from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class SwitchState(TypedDict):
    spec_requirements: dict
    validation_passed: bool
    error_log: list

def validate_switch_spec(state: SwitchState):
    specs = state['spec_requirements']
    errors = []
    if specs.get('load_capacity_amperes', 0) <= 0:
        errors.append('Invalid load capacity')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def route_by_validation(state: SwitchState):
    return 'process_success' if state['validation_passed'] else 'flag_error'

def process_success(state: SwitchState):
    print('Switch specification verified for procurement.')
    return state

def flag_error(state: SwitchState):
    print(f'Validation failed: {state["error_log"]}')
    return state

graph = StateGraph(SwitchState)
graph.add_node('validate', validate_switch_spec)
graph.add_node('process_success', process_success)
graph.add_node('flag_error', flag_error)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process_success', END)
graph.add_edge('flag_error', END)

# Compile the graph
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_requirements': {},
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
