from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChalkLineState(TypedDict):
    line_length: float
    casing_material: str
    is_valid: bool

def validate_specs(state: ChalkLineState):
    state['is_valid'] = state['line_length'] > 0 and state['casing_material'] != ''
    return state

def determine_workflow(state: ChalkLineState):
    return 'process' if state['is_valid'] else END

def process_tool(state: ChalkLineState):
    print(f'Processing chalk line of length {state['line_length']}m')
    return state

graph = StateGraph(ChalkLineState)
graph.add_node('validation', validate_specs)
graph.add_node('process', process_tool)
graph.set_entry_point('validation')
graph.add_conditional_edges('validation', determine_workflow)
graph.add_edge('process', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'line_length': 0.0,
    'casing_material': "",
    'is_valid': False
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
