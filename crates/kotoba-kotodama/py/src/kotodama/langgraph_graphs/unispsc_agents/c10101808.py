from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RawMaterialState(TypedDict):
    material_id: str
    sustainability_certified: bool
    inspection_passed: bool
    traceability_data: str
    processing_steps: List[str]

def validate_certification(state: RawMaterialState) -> RawMaterialState:
    state['sustainability_certified'] = True
    state['processing_steps'].append('certification_verified')
    return state

def perform_inspection(state: RawMaterialState) -> RawMaterialState:
    state['inspection_passed'] = True
    state['processing_steps'].append('material_inspected')
    return state

builder = StateGraph(RawMaterialState)
builder.add_node('certify', validate_certification)
builder.add_node('inspect', perform_inspection)
builder.add_edge('certify', 'inspect')
builder.add_edge('inspect', END)
builder.set_entry_point('certify')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'sustainability_certified': False,
    'inspection_passed': False,
    'traceability_data': "",
    'processing_steps': []
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
