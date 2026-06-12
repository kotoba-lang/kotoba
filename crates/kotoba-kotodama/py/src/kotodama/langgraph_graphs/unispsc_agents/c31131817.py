from langgraph.graph import StateGraph, END
from typing import TypedDict

class ForgeState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_geometry(state: ForgeState):
    # Simulate CAD/Dimension validation logic
    state['validation_passed'] = all(val > 0 for val in state['spec_data'].values())
    return state

def check_material_certs(state: ForgeState):
    # Verify metallurgical compliance
    has_certs = state['spec_data'].get('has_iso_cert', False)
    state['validation_passed'] = state['validation_passed'] and has_certs
    return state

graph = StateGraph(ForgeState)
graph.add_node('geometry_check', validate_geometry)
graph.add_node('cert_check', check_material_certs)
graph.set_entry_point('geometry_check')
graph.add_edge('geometry_check', 'cert_check')
graph.add_edge('cert_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
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
