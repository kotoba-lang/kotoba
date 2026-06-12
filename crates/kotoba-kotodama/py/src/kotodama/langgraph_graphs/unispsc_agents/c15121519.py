from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class GasState(TypedDict):
    purity: float
    pressure: float
    is_safe: bool
    log: list[str]

def validate_gas_purity(state: GasState) -> GasState:
    state['is_safe'] = state['purity'] >= 99.999
    state['log'].append(f'Purity check: {state["purity"]}% (Safe: {state["is_safe"]})')
    return state

def check_pressure_vessel(state: GasState) -> GasState:
    if state['pressure'] > 200:
        state['is_safe'] = False
        state['log'].append('Pressure exceeded safety limits')
    return state

graph = StateGraph(GasState)
graph.add_node('validate_purity', validate_gas_purity)
graph.add_node('check_pressure', check_pressure_vessel)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_pressure')
graph.add_edge('check_pressure', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'pressure': 0.0,
    'is_safe': False,
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
