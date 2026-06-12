from typing import TypedDict
from langgraph.graph import StateGraph, END

class LaserWeldState(TypedDict):
    spec_data: dict
    validation_results: dict
    is_compliant: bool

def validate_safety_protocols(state: LaserWeldState):
    # Simulate laser safety class check per ISO 11553
    state['validation_results'] = {'safety_check': state['spec_data'].get('class') == 'Class 4'}
    state['is_compliant'] = state['validation_results']['safety_check']
    return state

def perform_beam_check(state: LaserWeldState):
    # Simulate beam stability calculation
    state['validation_results']['beam_stab'] = "PASSED"
    return state

workflow = StateGraph(LaserWeldState)
workflow.add_node("safety_check", validate_safety_protocols)
workflow.add_node("beam_check", perform_beam_check)
workflow.set_entry_point("safety_check")
workflow.add_edge("safety_check", "beam_check")
workflow.add_edge("beam_check", END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_results': {},
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
