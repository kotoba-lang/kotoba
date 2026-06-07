from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class FastenerState(TypedDict):
    part_number: str
    material: str
    specs: Dict[str, Any]
    validation_log: List[str]
    is_compliant: bool

def validate_material(state: FastenerState) -> FastenerState:
    material = state.get('material', '').lower()
    if 'stainless' in material or 'steel' in material:
        state['validation_log'].append('Material validation passed.')
        state['is_compliant'] = True
    else:
        state['validation_log'].append('Material validation failed.')
        state['is_compliant'] = False
    return state

def check_standards(state: FastenerState) -> FastenerState:
    if state['is_compliant']:
        state['validation_log'].append('Standard compliance confirmed.')
    return state

builder = StateGraph(FastenerState)
builder.add_node('validate_material', validate_material)
builder.add_node('check_standards', check_standards)
builder.add_edge('validate_material', 'check_standards')
builder.add_edge('check_standards', END)
builder.set_entry_point('validate_material')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'material': "",
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
