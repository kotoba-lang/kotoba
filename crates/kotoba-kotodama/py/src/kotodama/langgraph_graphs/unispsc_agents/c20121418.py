from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    part_id: str
    specs: dict
    validation_passed: bool
    log: List[str]

def validate_specs(state: BearingState) -> BearingState:
    specs = state.get('specs', {})
    # Simulated strict validation for high-precision components
    if 'load_capacity' in specs and specs['load_capacity'] > 0:
        state['validation_passed'] = True
        state['log'].append('Specs validated successfully')
    else:
        state['validation_passed'] = False
        state['log'].append('Validation failed: Missing or invalid load capacity')
    return state

def quality_control(state: BearingState) -> BearingState:
    if state['validation_passed']:
        state['log'].append('Quality check passed for high-precision bearing')
    return state

builder = StateGraph(BearingState)
builder.add_node('validate', validate_specs)
builder.add_node('qc', quality_control)
builder.add_edge('validate', 'qc')
builder.add_edge('qc', END)
builder.set_entry_point('validate')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'specs': {},
    'validation_passed': False,
    'log': []
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
