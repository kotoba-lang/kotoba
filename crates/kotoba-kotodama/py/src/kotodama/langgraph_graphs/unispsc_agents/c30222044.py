from typing import TypedDict
from langgraph.graph import StateGraph, END

class RoadState(TypedDict):
    pavement_specs: dict
    compliance_report: str
    approval_status: bool

def validate_materials(state: RoadState):
    # Simulate material compliance check for ring road construction
    state['approval_status'] = 'durability' in state['pavement_specs']
    return state

def sign_off(state: RoadState):
    return {'compliance_report': 'Validated' if state['approval_status'] else 'Rejected'}

graph = StateGraph(RoadState)
graph.add_node('validate', validate_materials)
graph.add_node('sign_off', sign_off)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sign_off')
graph.add_edge('sign_off', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'pavement_specs': {},
    'compliance_report': "",
    'approval_status': False
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
