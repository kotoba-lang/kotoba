from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AluminumState(TypedDict):
    alloy_grade: str
    quality_checks: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_alloy_grade(state: AluminumState) -> AluminumState:
    # Logic to validate Aerospace grade aluminum spec compliance
    state['is_compliant'] = state['alloy_grade'] in ['7075-T6', '2024-T3']
    return state

def run_inspection_logic(state: AluminumState) -> AluminumState:
    # Simulate material property verification
    state['quality_checks'] = ['tensile_test_passed', 'ultrasonic_scan_complete']
    return state

builder = StateGraph(AluminumState)
builder.add_node('validate', validate_alloy_grade)
builder.add_node('inspect', run_inspection_logic)
builder.add_edge('validate', 'inspect')
builder.add_edge('inspect', END)
builder.set_entry_point('validate')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'alloy_grade': "",
    'quality_checks': [],
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
