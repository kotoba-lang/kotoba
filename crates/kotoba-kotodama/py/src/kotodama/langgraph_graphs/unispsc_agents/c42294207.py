from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SurgicalSetState(TypedDict):
    instrument_list: List[str]
    sterilization_status: str
    compliance_validated: bool

def validate_inventory(state: SurgicalSetState):
    # Business logic for instrument completeness
    return {'compliance_validated': len(state['instrument_list']) > 0}

def perform_quality_check(state: SurgicalSetState):
    # Business logic for sterilization compliance
    return {'sterilization_status': 'COMPLIANT'}

builder = StateGraph(SurgicalSetState)
builder.add_node('inventory', validate_inventory)
builder.add_node('quality', perform_quality_check)
builder.add_edge('inventory', 'quality')
builder.add_edge('quality', END)
builder.set_entry_point('inventory')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'instrument_list': [],
    'sterilization_status': "",
    'compliance_validated': False
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
