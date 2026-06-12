from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AdhesionState(TypedDict):
    material_spec: dict
    validation_results: Annotated[Sequence[str], operator.add]
    status: str

def validate_material(state: AdhesionState):
    spec = state['material_spec']
    results = []
    if spec.get('viscosity_cps', 0) < 100:
        results.append('CRITICAL_LOW_VISCOSITY')
    if spec.get('tensile_strength_mpa', 0) < 5:
        results.append('INSUFFICIENT_BOND_STRENGTH')
    return {'validation_results': results}

def process_workflow(state: AdhesionState):
    if 'CRITICAL_LOW_VISCOSITY' in state['validation_results']:
        return {'status': 'REJECTED_SAFETY_FAILURE'}
    return {'status': 'READY_FOR_ASSEMBLY'}

graph = StateGraph(AdhesionState)
graph.add_node('validate', validate_material)
graph.add_node('process', process_workflow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_spec': {},
    'validation_results': [],
    'status': ""
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
