from typing import TypedDict
from langgraph.graph import StateGraph, END

class WeldingScreenState(TypedDict):
    spec_data: dict
    approved: bool

def validate_materials(state: WeldingScreenState):
    # Check for flame retardant certification
    is_compliant = state['spec_data'].get('fire_rating') == 'UL-94'
    return {'approved': is_compliant}

def filter_light(state: WeldingScreenState):
    # Simulate UV blocking validation
    print('Validating optical hazard protection')
    return {'approved': state['approved'] and state['spec_data'].get('uv_blocking') > 95}

builder = StateGraph(WeldingScreenState)
builder.add_node('compliance', validate_materials)
builder.add_node('safety', filter_light)
builder.set_entry_point('compliance')
builder.add_edge('compliance', 'safety')
builder.add_edge('safety', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
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
