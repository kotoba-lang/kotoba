from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FrozenBerryState(TypedDict):
    batch_id: str
    temperature_logs: List[float]
    passed_inspection: bool

def validate_cold_chain(state: FrozenBerryState):
    temp_avg = sum(state['temperature_logs']) / len(state['temperature_logs'])
    return {'passed_inspection': temp_avg <= -18.0}

def update_inventory(state: FrozenBerryState):
    print(f'Batch {state['batch_id']} cleared for warehouse storage.')
    return {}

builder = StateGraph(FrozenBerryState)
builder.add_node('validate_cold_chain', validate_cold_chain)
builder.add_node('update_inventory', update_inventory)
builder.add_edge('validate_cold_chain', 'update_inventory')
builder.set_entry_point('validate_cold_chain')
builder.add_edge('update_inventory', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'temperature_logs': [],
    'passed_inspection': False
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
