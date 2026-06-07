from typing import TypedDict
from langgraph.graph import StateGraph, END

class PLCState(TypedDict):
    specs: dict
    validation_log: list
    is_compliant: bool

def validate_specs(state: PLCState):
    log = []
    required = ['bus_protocol_compatibility', 'IP_rating']
    valid = all(key in state['specs'] for key in required)
    log.append('Specs validated') if valid else log.append('Missing specs')
    return {'validation_log': log, 'is_compliant': valid}

def route_by_compliance(state: PLCState):
    return 'compliant_path' if state['is_compliant'] else 'reject_path'

graph = StateGraph(PLCState)
graph.add_node('validation', validate_specs)
graph.set_entry_point('validation')
graph.add_conditional_edges('validation', route_by_compliance, {'compliant_path': END, 'reject_path': END})
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'validation_log': [],
    'is_compliant': False
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
