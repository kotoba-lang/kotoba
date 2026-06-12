from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class LithoState(TypedDict):
    device_id: str
    compliance_docs: List[str]
    validation_passed: bool
    maintenance_cycle: int

def validate_specs(state: LithoState):
    state['validation_passed'] = 'ISO-13485' in state['compliance_docs']
    return state

def check_maintenance(state: LithoState):
    if state['maintenance_cycle'] > 12:
        state['validation_passed'] = False
    return state

graph = StateGraph(LithoState)
graph.add_node('validate', validate_specs)
graph.add_node('maintenance', check_maintenance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'maintenance')
graph.add_edge('maintenance', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'device_id': "",
    'compliance_docs': [],
    'validation_passed': False,
    'maintenance_cycle': 0
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
