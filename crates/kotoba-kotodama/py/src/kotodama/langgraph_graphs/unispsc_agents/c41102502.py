from typing import TypedDict
from langgraph.graph import StateGraph, END

class EntomologyGraphState(TypedDict):
    facility_specs: dict
    validation_passed: bool

def validate_environmental_specs(state: EntomologyGraphState):
    temp = state['facility_specs'].get('temperature', 0)
    state['validation_passed'] = 15 <= temp <= 35
    return state

def decision_node(state: EntomologyGraphState):
    return 'pass' if state['validation_passed'] else 'fail'

graph = StateGraph(EntomologyGraphState)
graph.add_node('validate', validate_environmental_specs)
graph.add_node('pass', lambda state: state)
graph.add_node('fail', lambda state: state)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', decision_node, {'pass': 'pass', 'fail': 'fail'})
graph.add_edge('pass', END)
graph.add_edge('fail', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'facility_specs': {},
    'validation_passed': False
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
