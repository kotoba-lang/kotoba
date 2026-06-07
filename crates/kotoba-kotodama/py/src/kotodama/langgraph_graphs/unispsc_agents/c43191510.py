from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class GPUProcState(TypedDict):
    gpu_id: str
    spec_requirements: dict
    validation_score: float

def validate_gpu_specs(state: GPUProcState) -> GPUProcState:
    # Logic to validate industrial GPU specs
    state['validation_score'] = 1.0 if 'thermal_design_power' in state['spec_requirements'] else 0.0
    return state

def optimize_configuration(state: GPUProcState) -> GPUProcState:
    # Logic to optimize power/performance for the specific application
    return state

builder = StateGraph(GPUProcState)
builder.add_node('validate', validate_gpu_specs)
builder.add_node('optimize', optimize_configuration)
builder.add_edge('validate', 'optimize')
builder.add_edge('optimize', END)
builder.set_entry_point('validate')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'gpu_id': "",
    'spec_requirements': {},
    'validation_score': 0.0
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
