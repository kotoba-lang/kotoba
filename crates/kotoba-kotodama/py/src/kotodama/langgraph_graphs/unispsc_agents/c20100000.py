from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class HeavyMachineryState(TypedDict):
    machinery_id: str
    inspection_status: str
    load_profile: float
    safety_logs: Annotated[list, add_messages]

def validate_machinery_spec(state: HeavyMachineryState):
    # Simulate CAD/spec validation logic for heavy machinery
    status = 'VALID' if state['load_profile'] < 10000 else 'MANUAL_REVIEW_REQUIRED'
    return {'inspection_status': status}

def deploy_safety_protocol(state: HeavyMachineryState):
    # Workflow step for safety compliance
    return {'safety_logs': ['Protocol Alpha Initialized for ' + state['machinery_id']]}

graph = StateGraph(HeavyMachineryState)
graph.add_node('validate', validate_machinery_spec)
graph.add_node('safety', deploy_safety_protocol)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)

# Compile the graph
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'machinery_id': "",
    'inspection_status': "",
    'load_profile': 0.0,
    'safety_logs': []
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
