from typing import TypedDict
from langgraph.graph import StateGraph, END

class CotSystemState(TypedDict):
    spec_data: dict
    validated: bool
    safety_report: str

def validate_safety_standards(state: CotSystemState):
    cert = state['spec_data'].get('safety_certification_standard')
    state['validated'] = cert in ['ASTM-F963', 'EN-71']
    return state

def check_hazard_testing(state: CotSystemState):
    if state['validated']:
        state['safety_report'] = 'PASS: Safety standards verified.'
    else:
        state['safety_report'] = 'FAIL: Missing or invalid certification.'
    return state

graph = StateGraph(CotSystemState)
graph.add_node('validate', validate_safety_standards)
graph.add_node('check', check_hazard_testing)
graph.set_entry_point('validate')
graph.add_edge('validate', 'check')
graph.add_edge('check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validated': False,
    'safety_report': ""
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
