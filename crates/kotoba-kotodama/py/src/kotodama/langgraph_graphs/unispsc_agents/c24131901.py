from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class IceMakerState(TypedDict):
    specs: dict
    validation_errors: List[str]
    approved: bool

def validate_capacity(state: IceMakerState):
    capacity = state['specs'].get('capacity', 0)
    if capacity < 20:
        state['validation_errors'].append('Insufficient capacity for commercial use')
    return state

def check_compliance(state: IceMakerState):
    if 'cert' not in state['specs']:
        state['validation_errors'].append('Missing safety certification')
    else:
        state['approved'] = True
    return state

graph = StateGraph(IceMakerState)
graph.add_node('capacity_check', validate_capacity)
graph.add_node('compliance_check', check_compliance)
graph.set_entry_point('capacity_check')
graph.add_edge('capacity_check', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'validation_errors': [],
    'approved': False
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
