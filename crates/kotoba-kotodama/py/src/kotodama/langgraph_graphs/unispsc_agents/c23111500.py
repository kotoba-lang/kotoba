from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MachineState(TypedDict):
    machine_specs: dict
    validation_errors: List[str]
    approved: bool

def validate_safety_specs(state: MachineState) -> MachineState:
    specs = state.get('machine_specs', {})
    if 'safety_light_curtain' not in specs:
        state['validation_errors'].append('Missing mandatory safety light curtain spec')
    return state

def check_capacity(state: MachineState) -> MachineState:
    if state['machine_specs'].get('tonnage', 0) <= 0:
        state['validation_errors'].append('Invalied tonnage capacity')
    return state

builder = StateGraph(MachineState)
builder.add_node('safety_check', validate_safety_specs)
builder.add_node('capacity_check', check_capacity)
builder.set_entry_point('safety_check')
builder.add_edge('safety_check', 'capacity_check')
builder.add_edge('capacity_check', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'machine_specs': {},
    'validation_errors': [],
    'approved': False
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
