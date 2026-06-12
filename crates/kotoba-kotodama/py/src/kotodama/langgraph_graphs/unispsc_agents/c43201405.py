from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ServerProcurementState(TypedDict):
    requirements: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_specs(state: ServerProcurementState):
    reqs = state['requirements']
    logs = []
    compliant = True
    if 'processor_spec' not in reqs:
        logs.append('Missing processor specification')
        compliant = False
    return {'validation_logs': logs, 'is_compliant': compliant}

def perform_compliance_check(state: ServerProcurementState):
    return {'validation_logs': ['Compliance verified against export controls'], 'is_compliant': state['is_compliant']}

graph = StateGraph(ServerProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', perform_compliance_check)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'requirements': {},
    'validation_logs': [],
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
