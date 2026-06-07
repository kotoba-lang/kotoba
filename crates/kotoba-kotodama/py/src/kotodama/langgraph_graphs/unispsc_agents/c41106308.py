from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PCRState(TypedDict):
    sequence: str
    purity_validated: bool
    thermal_profile: dict
    approved: bool

def validate_sequence(state: PCRState):
    # Business logic for sequence validation
    if len(state['sequence']) > 15:
        return {'purity_validated': True}
    return {'purity_validated': False}

def check_thermal_compliance(state: PCRState):
    # Logic to confirm Tm compatibility
    return {'approved': state['purity_validated']}

graph = StateGraph(PCRState)
graph.add_node("validate", validate_sequence)
graph.add_node("thermal", check_thermal_compliance)
graph.add_edge("validate", "thermal")
graph.add_edge("thermal", END)
graph.set_entry_point("validate")
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'sequence': "",
    'purity_validated': False,
    'thermal_profile': {},
    'approved': False
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
