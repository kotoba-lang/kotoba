from typing import TypedDict
from langgraph.graph import StateGraph, END

class LightingState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_dmx_protocol(state: LightingState):
    protocol = state['spec_data'].get('protocol')
    return {'validated': protocol == 'DMX512', 'error_log': [] if protocol == 'DMX512' else ['Invalid Protocol']}

def check_safety_compliance(state: LightingState):
    certified = state['spec_data'].get('safety_cert')
    return {'validated': state['validated'] and certified, 'error_log': state['error_log'] + ([] if certified else ['Missing Safety Cert'])}

builder = StateGraph(LightingState)
builder.add_node('dmx_check', validate_dmx_protocol)
builder.add_node('safety_check', check_safety_compliance)
builder.set_entry_point('dmx_check')
builder.add_edge('dmx_check', 'safety_check')
builder.add_edge('safety_check', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validated': False,
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
