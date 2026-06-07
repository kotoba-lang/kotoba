from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class ValveState(TypedDict):
    specs: dict
    validation_log: Annotated[list, operator.add]
    is_compliant: bool

def validate_pressure_rating(state: ValveState):
    pressure = state['specs'].get('pressure', 0)
    is_valid = pressure > 0
    return {'validation_log': [f'Pressure check: {pressure} bar'], 'is_compliant': is_valid}

def check_material_safety(state: ValveState):
    material = state['specs'].get('body_material', 'unknown')
    is_safe = material in ['SUS304', 'SUS316', 'Cast Iron']
    return {'validation_log': [f'Material check: {material}'], 'is_compliant': is_safe}

graph = StateGraph(ValveState)
graph.add_node('pressure_check', validate_pressure_rating)
graph.add_node('material_check', check_material_safety)
graph.set_entry_point('pressure_check')
graph.add_edge('pressure_check', 'material_check')
graph.add_edge('material_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'validation_log': [],
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
