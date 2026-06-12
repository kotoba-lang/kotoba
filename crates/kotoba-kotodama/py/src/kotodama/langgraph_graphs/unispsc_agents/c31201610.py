from typing import TypedDict
from langgraph.graph import StateGraph, END

class GlueState(TypedDict):
    material_name: str
    chemical_data: dict
    compliance_ok: bool

def validate_safety(state: GlueState):
    # Simulate SDS and hazardous material validation
    is_compliant = 'restricted' not in state['chemical_data'].get('components', [])
    return {'compliance_ok': is_compliant}

def process_glue(state: GlueState):
    print(f'Processing glue: {state.get("material_name")}')
    return {}

builder = StateGraph(GlueState)
builder.add_node('validate', validate_safety)
builder.add_node('process', process_glue)
builder.set_entry_point('validate')
builder.add_edge('validate', 'process')
builder.add_edge('process', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_name': "",
    'chemical_data': {},
    'compliance_ok': False
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
