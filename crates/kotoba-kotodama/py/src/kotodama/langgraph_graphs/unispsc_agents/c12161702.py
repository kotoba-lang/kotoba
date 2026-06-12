from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class MetalPowderState(TypedDict):
    commodity_code: str
    spec_data: dict
    validation_log: Annotated[list[str], operator.add]
    status: str

def validate_purity(state: MetalPowderState):
    purity = state['spec_data'].get('purity', 0)
    if purity < 99.9:
        return {'validation_log': ['Purity level insufficient'], 'status': 'REJECTED'}
    return {'validation_log': ['Purity validated'], 'status': 'PASSED'}

def export_control_check(state: MetalPowderState):
    if state['spec_data'].get('dual_use', False):
        return {'validation_log': ['Dual-use control triggered'], 'status': 'REVIEW_REQUIRED'}
    return {'validation_log': ['Export control cleared'], 'status': 'PASSED'}

builder = StateGraph(MetalPowderState)
builder.add_node('validate', validate_purity)
builder.add_node('control', export_control_check)
builder.set_entry_point('validate')
builder.add_edge('validate', 'control')
builder.add_edge('control', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'spec_data': {},
    'validation_log': [],
    'status': ""
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
