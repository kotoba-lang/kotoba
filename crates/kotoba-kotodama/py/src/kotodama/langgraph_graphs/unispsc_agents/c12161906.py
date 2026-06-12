from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ResinProcessingState(TypedDict):
    batch_id: str
    viscosity: float
    purity_level: float
    quality_passed: bool
    logs: List[str]

def validate_viscosity(state: ResinProcessingState):
    passed = 80.0 <= state['viscosity'] <= 120.0
    return {'quality_passed': passed, 'logs': [f'Viscosity check: {passed}']}

def check_purity(state: ResinProcessingState):
    passed = state['purity_level'] >= 0.999
    return {'quality_passed': state['quality_passed'] and passed, 'logs': state['logs'] + [f'Purity check: {passed}']}

builder = StateGraph(ResinProcessingState)
builder.add_node('validate_viscosity', validate_viscosity)
builder.add_node('check_purity', check_purity)
builder.set_entry_point('validate_viscosity')
builder.add_edge('validate_viscosity', 'check_purity')
builder.add_edge('check_purity', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'viscosity': 0.0,
    'purity_level': 0.0,
    'quality_passed': False,
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
