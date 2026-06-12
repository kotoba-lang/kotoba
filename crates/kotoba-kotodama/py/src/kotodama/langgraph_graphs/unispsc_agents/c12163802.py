from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SemiconductorChemState(TypedDict):
    purity_level: float
    safety_clearance: bool
    validation_logs: Annotated[Sequence[str], operator.add]

def validate_purity(state: SemiconductorChemState):
    # Simulated precision check for 12163802 semiconductor grade reagents
    is_pure = state['purity_level'] >= 99.999
    return {'safety_clearance': is_pure, 'validation_logs': ['Purity check completed']}

def check_safety_protocols(state: SemiconductorChemState):
    logs = ['Protocol verified'] if state['safety_clearance'] else ['CRITICAL: Purity failure']
    return {'validation_logs': logs}

builder = StateGraph(SemiconductorChemState)
builder.add_node('validate', validate_purity)
builder.add_node('safety', check_safety_protocols)
builder.add_edge('validate', 'safety')
builder.add_edge('safety', END)
builder.set_entry_point('validate')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'safety_clearance': False,
    'validation_logs': []
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
