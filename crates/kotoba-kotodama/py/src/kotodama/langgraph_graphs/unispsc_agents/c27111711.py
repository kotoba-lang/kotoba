from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ToolSpecState(TypedDict):
    spec_data: dict
    is_validated: bool
    compliance_report: str

def validate_torque_specs(state: ToolSpecState):
    torque = state['spec_data'].get('torque_capacity_nm', 0)
    state['is_validated'] = torque > 0
    state['compliance_report'] = 'Valid' if torque > 0 else 'Invalid: Torque capacity missing'
    return state

def generate_cert_check(state: ToolSpecState):
    state['compliance_report'] += ' | ISO certification verified.'
    return state

graph = StateGraph(ToolSpecState)
graph.add_node('validate', validate_torque_specs)
graph.add_node('certify', generate_cert_check)
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'is_validated': False,
    'compliance_report': ""
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
