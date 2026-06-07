from typing import TypedDict
from langgraph.graph import StateGraph, END

class InductionDryerState(TypedDict):
    temp_req: float
    safety_check_passed: bool
    validation_log: list

def validate_specs(state: InductionDryerState):
    passed = state['temp_req'] > 0
    return {'safety_check_passed': passed, 'validation_log': ['Specs validated']}

def conduct_risk_assessment(state: InductionDryerState):
    return {'validation_log': state['validation_log'] + ['Risk assessment complete']}

builder = StateGraph(InductionDryerState)
builder.add_node('specs', validate_specs)
builder.add_node('risk', conduct_risk_assessment)
builder.add_edge('specs', 'risk')
builder.add_edge('risk', END)
builder.set_entry_point('specs')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'temp_req': 0.0,
    'safety_check_passed': False,
    'validation_log': []
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
