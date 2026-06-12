from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RubberState(TypedDict):
    material_code: str
    viscosity: float
    purity_level: float
    qc_passed: bool
    validation_log: List[str]

def validate_viscosity(state: RubberState) -> RubberState:
    if 5.0 <= state['viscosity'] <= 50.0:
        state['validation_log'].append('Viscosity within operational tolerance.')
    else:
        state['validation_log'].append('Viscosity failure.')
    return state

def check_purity(state: RubberState) -> RubberState:
    if state['purity_level'] > 0.99:
        state['qc_passed'] = True
        state['validation_log'].append('Purity standards met for medical/aerospace.')
    return state

graph = StateGraph(RubberState)
graph.add_node('validate', validate_viscosity)
graph.add_node('purity', check_purity)
graph.add_edge('validate', 'purity')
graph.add_edge('purity', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_code': "",
    'viscosity': 0.0,
    'purity_level': 0.0,
    'qc_passed': False,
    'validation_log': []
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
