from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity_code: str
    spec_requirements: List[str]
    validation_results: List[str]
    is_compliant: bool

def validate_spec(state: ProcurementState) -> ProcurementState:
    # Logic to validate commodity specifications against standards
    results = [f'Validating {req}' for req in state['spec_requirements']]
    return {**state, 'validation_results': results, 'is_compliant': True}

def perform_risk_check(state: ProcurementState) -> ProcurementState:
    # Logic for risk tagging based on spec fields
    return {**state, 'is_compliant': True}

builder = StateGraph(ProcurementState)
builder.add_node('validate', validate_spec)
builder.add_node('risk_check', perform_risk_check)
builder.add_edge('validate', 'risk_check')
builder.add_edge('risk_check', END)
builder.set_entry_point('validate')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'spec_requirements': [],
    'validation_results': [],
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
