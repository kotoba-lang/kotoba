from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CarbonFiberState(TypedDict):
    material_id: str
    spec_requirements: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_tensile_strength(state: CarbonFiberState):
    strength = state['spec_requirements'].get('tensile_strength_mpa', 0)
    if strength >= 3500:
        return {'validation_results': ['Tensile strength meets aerospace grade']}
    return {'validation_results': ['Tensile strength below aerospace requirements']}

def check_certification(state: CarbonFiberState):
    certs = state['spec_requirements'].get('certs', [])
    if 'AS9100' in certs:
        return {'is_approved': True}
    return {'is_approved': False}

graph = StateGraph(CarbonFiberState)
graph.add_node('validate_physics', validate_tensile_strength)
graph.add_node('check_compliance', check_certification)
graph.add_edge('validate_physics', 'check_compliance')
graph.add_edge('check_compliance', END)
graph.set_entry_point('validate_physics')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
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
