from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FittingState(TypedDict):
    tool_list: List[str]
    validation_status: str
    is_compliant: bool

def validate_specs(state: FittingState):
    compliant = all([item.startswith('CERT-') for item in state['tool_list']])
    return {'validation_status': 'verified' if compliant else 'rejected', 'is_compliant': compliant}

def update_records(state: FittingState):
    print(f'Updating procurement logs for tools: {state['tool_list']}')
    return {'validation_status': 'recorded'}

graph = StateGraph(FittingState)
graph.add_node('validation', validate_specs)
graph.add_node('log', update_records)
graph.set_entry_point('validation')
graph.add_edge('validation', 'log')
graph.add_edge('log', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'tool_list': [],
    'validation_status': "",
    'is_compliant': False
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
