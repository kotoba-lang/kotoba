from typing import TypedDict
from langgraph.graph import StateGraph, END

class AircraftState(TypedDict):
    inspection_passed: bool
    compliance_docs: list
    next_step: str

def validate_specs(state: AircraftState):
    state['inspection_passed'] = len(state['compliance_docs']) > 3
    return {'next_step': 'approval' if state['inspection_passed'] else 'rejection'}

def approve_procurement(state: AircraftState):
    return {'next_step': 'finalized'}

workflow = StateGraph(AircraftState)
workflow.add_node("validate", validate_specs)
workflow.add_node("approve", approve_procurement)
workflow.set_entry_point("validate")
workflow.add_edge("validate", "approve")
workflow.add_edge("approve", END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'inspection_passed': False,
    'compliance_docs': [],
    'next_step': ""
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
