from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class LubricantState(TypedDict):
    spec_sheet: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_viscosity(state: LubricantState):
    val = state['spec_sheet'].get('kinematic_viscosity_cst', 0)
    status = 'PASS' if 50 <= val <= 500 else 'FAIL'
    return {'validation_results': [f'Viscosity: {status}']}

def check_flash_point(state: LubricantState):
    fp = state['spec_sheet'].get('flash_point_celsius', 0)
    status = 'PASS' if fp >= 200 else 'FAIL'
    return {'validation_results': [f'FlashPoint: {status}']}

def finalize_check(state: LubricantState):
    passed = all('PASS' in res for res in state['validation_results'])
    return {'is_approved': passed}

builder = StateGraph(LubricantState)
builder.add_node('viscosity', validate_viscosity)
builder.add_node('flash_point', check_flash_point)
builder.add_node('finalize', finalize_check)
builder.set_entry_point('viscosity')
builder.add_edge('viscosity', 'flash_point')
builder.add_edge('flash_point', 'finalize')
builder.add_edge('finalize', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_sheet': {},
    'validation_results': [],
    'is_approved': False
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
