from typing import TypedDict
from langgraph.graph import StateGraph, END

class MissileState(TypedDict):
    spec_data: dict
    security_cleared: bool
    validation_log: list

def validate_specs(state: MissileState):
    # Business logic for critical defense specs
    valid = all(key in state['spec_data'] for key in ['guidance', 'payload'])
    return {'validation_log': [f'Specs valid: {valid}'], 'security_cleared': valid}

def security_checkpoint(state: MissileState):
    # Regulatory and sanctions check
    return {'security_cleared': state.get('security_cleared', False)}

graph = StateGraph(MissileState)
graph.add_node('validate', validate_specs)
graph.add_node('security', security_checkpoint)
graph.set_entry_point('validate')
graph.add_edge('validate', 'security')
graph.add_edge('security', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'security_cleared': False,
    'validation_log': []
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
