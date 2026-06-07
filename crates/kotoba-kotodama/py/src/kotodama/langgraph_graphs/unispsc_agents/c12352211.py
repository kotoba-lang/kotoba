from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AdhesionState(TypedDict):
    material_code: str
    viscosity_ok: bool
    safety_check_passed: bool
    log: List[str]

def validate_viscosity(state: AdhesionState):
    # Simulate CAD/Spec validation logic
    state['viscosity_ok'] = True
    state['log'].append('Viscosity validated against industry specs.')
    return state

def run_safety_protocol(state: AdhesionState):
    # Simulate handling dangerous goods
    state['safety_check_passed'] = True
    state['log'].append('Chemical safety classification passed.')
    return state

builder = StateGraph(AdhesionState)
builder.add_node('validate', validate_viscosity)
builder.add_node('safety', run_safety_protocol)
builder.set_entry_point('validate')
builder.add_edge('validate', 'safety')
builder.add_edge('safety', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_code': "",
    'viscosity_ok': False,
    'safety_check_passed': False,
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
