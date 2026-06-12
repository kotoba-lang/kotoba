from typing import TypedDict
from langgraph.graph import StateGraph, END

class IRState(TypedDict):
    specs: dict
    validated: bool
    export_cleared: bool

def validate_specs(state: IRState):
    cooling_cap = state['specs'].get('cooling_cap', 0)
    state['validated'] = cooling_cap > 0
    return state

def check_export(state: IRState):
    eccn = state['specs'].get('eccn', '')
    state['export_cleared'] = eccn == '6A002'
    return state

graph = StateGraph(IRState)
graph.add_node('validate_specs', validate_specs)
graph.add_node('check_export', check_export)
graph.set_entry_point('validate_specs')
graph.add_edge('validate_specs', 'check_export')
graph.add_edge('check_export', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'validated': False,
    'export_cleared': False
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
