from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class OilDipstickState(TypedDict):
    part_number: str
    material_specs: dict
    validation_results: List[str]
    is_approved: bool

def validate_dimensional_accuracy(state: OilDipstickState):
    # Simulate CAD/DIM validation logic
    tolerance = state['material_specs'].get('tolerance_mm', 0.05)
    status = f'Validated accuracy within {tolerance}mm' if tolerance <= 0.1 else 'Validation Failed'
    return {'validation_results': [status], 'is_approved': tolerance <= 0.1}

workflow = StateGraph(OilDipstickState)
workflow.add_node('validate_dims', validate_dimensional_accuracy)
workflow.set_entry_point('validate_dims')
workflow.add_edge('validate_dims', END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'material_specs': {},
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
