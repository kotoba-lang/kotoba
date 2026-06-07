from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class StrappingState(TypedDict):
    spec_data: dict
    validation_passed: bool
    errors: List[str]

def validate_tensile_strength(state: StrappingState):
    strength = state['spec_data'].get('tensile_strength', 0)
    if strength < 500:
        return {'validation_passed': False, 'errors': ['Insufficient tensile strength']}
    return {'validation_passed': True}

def check_material_compliance(state: StrappingState):
    material = state['spec_data'].get('material', '')
    if material not in ['Steel', 'Stainless Steel']:
        return {'validation_passed': False, 'errors': ['Unsupported material type']}
    return {'validation_passed': True}

graph = StateGraph(StrappingState)
graph.add_node('validate_strength', validate_tensile_strength)
graph.add_node('validate_material', check_material_compliance)
graph.set_entry_point('validate_strength')
graph.add_edge('validate_strength', 'validate_material')
graph.add_edge('validate_material', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_passed': False,
    'errors': []
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
