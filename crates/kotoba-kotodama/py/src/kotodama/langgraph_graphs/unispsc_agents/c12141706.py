from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AdhesiveState(TypedDict):
    material_code: str
    viscosity: float
    is_verified: bool
    process_steps: List[str]

def validate_viscosity(state: AdhesiveState) -> AdhesiveState:
    # Specialized check for robotic dispensing tolerance
    state['is_verified'] = 500 <= state['viscosity'] <= 1500
    return state

def plan_dispensing(state: AdhesiveState) -> AdhesiveState:
    if state['is_verified']:
        state['process_steps'] = ['surface_prep', 'robotic_dispense', 'uv_cure', 'thermal_curing']
    else:
        state['process_steps'] = ['request_retest']
    return state

builder = StateGraph(AdhesiveState)
builder.add_node('validate', validate_viscosity)
builder.add_node('plan', plan_dispensing)
builder.set_entry_point('validate')
builder.add_edge('validate', 'plan')
builder.add_edge('plan', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_code': "",
    'viscosity': 0.0,
    'is_verified': False,
    'process_steps': []
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
