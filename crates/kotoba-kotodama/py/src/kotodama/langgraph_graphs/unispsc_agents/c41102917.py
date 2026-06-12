from typing import TypedDict
from langgraph.graph import StateGraph, END
class ValidationState(TypedDict):
    blade_type: str
    iso_compliant: bool
    passed_safety_check: bool
def check_compliance(state: ValidationState):
    state['iso_compliant'] = True if state.get('iso_compliant') else False
    return {'iso_compliant': state['iso_compliant']}
def verify_blade(state: ValidationState):
    state['passed_safety_check'] = state['blade_type'] in ['tungsten', 'steel']
    return {'passed_safety_check': state['passed_safety_check']}
graph = StateGraph(ValidationState)
graph.add_node('compliance', check_compliance)
graph.add_node('safety', verify_blade)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'blade_type': "",
    'iso_compliant': False,
    'passed_safety_check': False
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
