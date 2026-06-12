from typing import TypedDict
from langgraph.graph import StateGraph, END

class HexNutState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_material(state: HexNutState):
    grade = state['spec_data'].get('material_grade')
    is_valid = grade in ['Grade 5', 'Grade 8', 'A4-70', 'Class 8.8']
    return {'validation_passed': is_valid}

def validate_dimensions(state: HexNutState):
    tolerance = state['spec_data'].get('tolerance')
    is_valid = tolerance <= 0.05
    return {'validation_passed': state['validation_passed'] and is_valid}

graph = StateGraph(HexNutState)
graph.add_node('validate_material', validate_material)
graph.add_node('validate_dimensions', validate_dimensions)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'validate_dimensions')
graph.add_edge('validate_dimensions', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_passed': False,
    'error_log': []
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
