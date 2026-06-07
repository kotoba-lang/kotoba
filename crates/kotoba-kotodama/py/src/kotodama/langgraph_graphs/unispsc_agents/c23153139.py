from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class WeldingState(TypedDict):
    process_id: str
    parameters: dict
    quality_metrics: List[float]
    is_compliant: bool

def validate_parameters(state: WeldingState) -> WeldingState:
    # Simulate CAD trajectory and welding parameter validation
    state['is_compliant'] = state['parameters'].get('voltage', 0) > 10.0
    return state

def execute_welding_cycle(state: WeldingState) -> WeldingState:
    # Simulate robot motion control execution
    state['quality_metrics'] = [0.98, 0.99] if state['is_compliant'] else [0.0, 0.0]
    return state

builder = StateGraph(WeldingState)
builder.add_node('validate', validate_parameters)
builder.add_node('execute', execute_welding_cycle)
builder.set_entry_point('validate')
builder.add_edge('validate', 'execute')
builder.add_edge('execute', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'process_id': "",
    'parameters': {},
    'quality_metrics': [],
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
