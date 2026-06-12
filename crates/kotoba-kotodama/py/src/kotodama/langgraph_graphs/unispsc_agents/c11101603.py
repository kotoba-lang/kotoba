from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CarbonFiberState(TypedDict):
    spec_requirements: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_tensile_strength(state: CarbonFiberState):
    strength = state['spec_requirements'].get('tensile_strength_mpa', 0)
    if strength >= 3500:
        return {'validation_results': ['Tensile strength meets aerospace grade'], 'is_compliant': True}
    return {'validation_results': ['Tensile strength insufficient'], 'is_compliant': False}

def verify_certification(state: CarbonFiberState):
    certs = state['spec_requirements'].get('certification_standard', [])
    if 'AS9100' in certs:
        return {'validation_results': ['Certification verified']}
    return {'validation_results': ['Certification missing']}

graph = StateGraph(CarbonFiberState)
graph.add_node('validate_strength', validate_tensile_strength)
graph.add_node('verify_certs', verify_certification)
graph.set_entry_point('validate_strength')
graph.add_edge('validate_strength', 'verify_certs')
graph.add_edge('verify_certs', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_requirements': {},
    'validation_results': [],
    'is_compliant': False
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
