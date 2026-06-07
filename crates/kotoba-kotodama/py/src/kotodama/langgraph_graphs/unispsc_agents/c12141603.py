from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class InorganicProcessState(TypedDict):
    purity_level: float
    particle_size_micron: float
    validation_passed: bool
    log: List[str]

def validate_purity(state: InorganicProcessState):
    passed = state['purity_level'] >= 99.9
    return {'validation_passed': passed, 'log': [f'Purity check: {passed}']}

def check_particle_specs(state: InorganicProcessState):
    passed = 0.5 <= state['particle_size_micron'] <= 50.0
    return {'validation_passed': passed and state['validation_passed'], 'log': state['log'] + [f'Particle spec check: {passed}']}

graph = StateGraph(InorganicProcessState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_particle', check_particle_specs)
graph.add_edge('validate_purity', 'check_particle')
graph.add_edge('check_particle', END)
graph.set_entry_point('validate_purity')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'particle_size_micron': 0.0,
    'validation_passed': False,
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
