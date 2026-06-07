from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AssayState(TypedDict):
    lot_number: str
    quality_status: str
    requires_cold_chain: bool

def validate_lot(state: AssayState):
    print(f'Validating lot: {state["lot_number"]}')
    return {'quality_status': 'verified'}

def check_temp(state: AssayState):
    print('Checking cold chain requirements...')
    return {'requires_cold_chain': True}

graph = StateGraph(AssayState)
graph.add_node('Validate', validate_lot)
graph.add_node('ColdChain', check_temp)
graph.add_edge('Validate', 'ColdChain')
graph.add_edge('ColdChain', END)
graph.set_entry_point('Validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'lot_number': "",
    'quality_status': "",
    'requires_cold_chain': False
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
