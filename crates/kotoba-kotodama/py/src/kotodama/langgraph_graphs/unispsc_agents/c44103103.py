from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TonerState(TypedDict):
    model_number: str
    yield_specs: dict
    compatibility_verified: bool

def validate_toner_specs(state: TonerState):
    # Business logic for toner compatibility mapping
    state['compatibility_verified'] = state['model_number'] in ['PRT-X1', 'PRT-Y2']
    return state

def check_sustainability(state: TonerState):
    print('Checking environmental credentials')
    return state

graph = StateGraph(TonerState)
graph.add_node('validate', validate_toner_specs)
graph.add_node('sustainability', check_sustainability)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sustainability')
graph.add_edge('sustainability', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'model_number': "",
    'yield_specs': {},
    'compatibility_verified': False
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
