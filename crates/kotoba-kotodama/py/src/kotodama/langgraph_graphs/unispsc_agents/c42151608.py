from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalTrayState(TypedDict):
    material: str
    is_autoclavable: bool
    validation_passed: bool

def validate_material(state: DentalTrayState):
    # Business logic for dental grade materials
    valid_materials = ['304_stainless', 'polypropylene', 'medical_grade_plastic']
    return {'validation_passed': state['material'] in valid_materials}

def check_autoclave_req(state: DentalTrayState):
    # Ensure dental sterilization compliance
    return {'validation_passed': state['validation_passed'] and state['is_autoclavable']}

graph = StateGraph(DentalTrayState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_autoclave', check_autoclave_req)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'check_autoclave')
graph.add_edge('check_autoclave', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material': "",
    'is_autoclavable': False,
    'validation_passed': False
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
