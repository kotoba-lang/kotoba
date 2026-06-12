from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SatelliteState(TypedDict):
    orbit_data: dict
    security_clearance: bool
    compliance_docs: List[str]

def validate_orbit(state: SatelliteState):
    # Perform check on orbital parameters compatibility
    return {'orbit_data': state['orbit_data']}

def check_compliance(state: SatelliteState):
    # Validate ITAR/EAR compliance protocols
    return {'compliance_docs': ['validated']}

graph = StateGraph(SatelliteState)
graph.add_node('validate_orbit', validate_orbit)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('validate_orbit')
graph.add_edge('validate_orbit', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'orbit_data': {},
    'security_clearance': False,
    'compliance_docs': []
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
