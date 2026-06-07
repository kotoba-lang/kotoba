from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AdhesiveState(TypedDict):
    spec_requirements: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_viscosity(state: AdhesiveState) -> AdhesiveState:
    val = state['spec_requirements'].get('viscosity_cps', 0)
    status = 'PASS' if 500 <= val <= 2000 else 'FAIL'
    return {'validation_results': [f'Viscosity: {status}']}

def validate_temp_range(state: AdhesiveState) -> AdhesiveState:
    r = state['spec_requirements'].get('operating_temp_range_celsius', [0, 0])
    status = 'PASS' if r[0] < -40 and r[1] > 150 else 'FAIL'
    return {'validation_results': [f'TempRange: {status}']}

def check_final_approval(state: AdhesiveState) -> str:
    if all('PASS' in res for res in state['validation_results']):
        return 'approved'
    return 'rejected'

graph = StateGraph(AdhesiveState)
graph.add_node('val_viscosity', validate_viscosity)
graph.add_node('val_temp', validate_temp_range)
graph.add_edge('val_viscosity', 'val_temp')
graph.add_conditional_edges('val_temp', check_final_approval, {'approved': END, 'rejected': END})
graph.set_entry_point('val_viscosity')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_requirements': {},
    'validation_results': [],
    'is_approved': False
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
