from typing import TypedDict
from langgraph.graph import StateGraph, END

class BloodBankState(TypedDict):
    lot_id: str
    temp_log: list
    qc_passed: bool

def validate_cold_chain(state: BloodBankState):
    # Business logic for cold chain monitoring verification
    return {'qc_passed': all(t < 8.0 for t in state['temp_log'])} if state['temp_log'] else {'qc_passed': False}

def update_inventory(state: BloodBankState):
    print(f'Updating inventory for lot: {state.get('lot_id')}')
    return {}

graph = StateGraph(BloodBankState)
graph.add_node('cold_chain', validate_cold_chain)
graph.add_node('inventory', update_inventory)
graph.set_entry_point('cold_chain')
graph.add_edge('cold_chain', 'inventory')
graph.add_edge('inventory', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'lot_id': "",
    'temp_log': [],
    'qc_passed': False
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
