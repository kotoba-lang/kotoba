from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END

class MaterialState(TypedDict):
    material_id: str
    specs: dict
    validation_score: float
    approved: bool

def validate_material_specs(state: MaterialState) -> MaterialState:
    # Logic to check material specifications against required thresholds
    specs = state['specs']
    if specs.get('tensile_strength_mpa', 0) > 3000:
        state['validation_score'] = 1.0
        state['approved'] = True
    else:
        state['validation_score'] = 0.5
        state['approved'] = False
    return state

def check_regulatory_compliance(state: MaterialState) -> MaterialState:
    # Logic to check if export control or material safety standards are met
    if state.get('approved', False):
        # Simulation of compliance check
        pass
    return state

workflow = StateGraph(MaterialState)
workflow.add_node('validate', validate_material_specs)
workflow.add_node('compliance', check_regulatory_compliance)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'compliance')
workflow.add_edge('compliance', END)

graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'specs': {},
    'validation_score': 0.0,
    'approved': False
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
