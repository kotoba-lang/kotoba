from typing import TypedDict
from langgraph.graph import StateGraph, END

class RocketState(TypedDict):
    spec_data: dict
    validation_flags: dict

def validate_propellant(state: RocketState):
    is_valid = state['spec_data'].get('propellant_type') in ['HTPB', 'Composite']
    return {'validation_flags': {'propellant': is_valid}}

def check_compliance(state: RocketState):
    is_compliant = state['spec_data'].get('itar_compliance_status') == 'Verified'
    return {'validation_flags': {'compliance': is_compliant}}

graph = StateGraph(RocketState)
graph.add_node('val_prop', validate_propellant)
graph.add_node('check_comp', check_compliance)
graph.set_entry_point('val_prop')
graph.add_edge('val_prop', 'check_comp')
graph.add_edge('check_comp', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_flags': {}
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
