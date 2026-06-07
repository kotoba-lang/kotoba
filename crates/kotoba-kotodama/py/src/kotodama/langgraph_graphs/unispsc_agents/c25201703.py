from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CountermeasureState(TypedDict):
    specs: dict
    compliance_validated: bool
    export_license_granted: bool
    final_approval: bool

def validate_tech_specs(state: CountermeasureState):
    # Simulate CAD/Military spec validation logic
    state['compliance_validated'] = all(k in state['specs'] for k in ['MIL-SPEC', 'range'])
    print('Specs Validated')
    return state

def check_export_controls(state: CountermeasureState):
    # Business logic for restricted goods export lookup
    state['export_license_granted'] = True
    return state

graph = StateGraph(CountermeasureState)
graph.add_node('validate_specs', validate_tech_specs)
graph.add_node('check_export', check_export_controls)
graph.set_entry_point('validate_specs')
graph.add_edge('validate_specs', 'check_export')
graph.add_edge('check_export', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'compliance_validated': False,
    'export_license_granted': False,
    'final_approval': False
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
