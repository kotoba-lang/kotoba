from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SiCState(TypedDict):
    purity: float
    particle_size: float
    validated: bool
    logs: List[str]

def validate_purity(state: SiCState) -> SiCState:
    if state['purity'] >= 99.5:
        state['validated'] = True
        state['logs'].append('Purity check passed')
    else:
        state['validated'] = False
        state['logs'].append('Purity check failed')
    return state

def check_particle_specs(state: SiCState) -> SiCState:
    if 0.1 <= state['particle_size'] <= 50.0:
        state['logs'].append('Particle size within tolerance')
    else:
        state['logs'].append('Particle size out of spec')
    return state

builder = StateGraph(SiCState)
builder.add_node('validate_purity', validate_purity)
builder.add_node('check_particle', check_particle_specs)
builder.set_entry_point('validate_purity')
builder.add_edge('validate_purity', 'check_particle')
builder.add_edge('check_particle', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'particle_size': 0.0,
    'validated': False,
    'logs': []
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
