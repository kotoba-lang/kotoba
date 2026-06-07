from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ToolingState(TypedDict):
    part_number: str
    spec_check: bool
    validation_logs: list[str]
    approved: bool

def validate_specs(state: ToolingState) -> ToolingState:
    # Logic for checking torque and payload parameters against safety limits
    state['spec_check'] = True
    state['validation_logs'].append('Payload and torque limits verified.')
    return state

def assembly_compatibility_check(state: ToolingState) -> ToolingState:
    # Logic to verify compatibility with specific robot arm interfaces
    state['approved'] = True
    state['validation_logs'].append('Interface compatibility confirmed.')
    return state

graph = StateGraph(ToolingState)
graph.add_node('validate', validate_specs)
graph.add_node('compatibility', assembly_compatibility_check)
graph.add_edge('validate', 'compatibility')
graph.add_edge('compatibility', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'spec_check': False,
    'validation_logs': [],
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
