from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class EnergyState(TypedDict):
    commodity_code: str
    volume: float
    safety_clearance: bool
    validation_log: Annotated[Sequence[str], operator.add]

def validate_fuel_safety(state: EnergyState) -> EnergyState:
    # Specialized validation logic for fuel handling
    if state['volume'] > 10000:
        return {'safety_clearance': False, 'validation_log': ['Volume exceeds industrial safety limit']}
    return {'safety_clearance': True, 'validation_log': ['Safety clearance passed']}

def route_by_safety(state: EnergyState) -> str:
    return 'process' if state['safety_clearance'] else 'halt'

def process_fuel_procurement(state: EnergyState) -> EnergyState:
    return {'validation_log': ['Processing fuel logistics chain']}

builder = StateGraph(EnergyState)
builder.add_node('validate', validate_fuel_safety)
builder.add_node('process', process_fuel_procurement)
builder.set_entry_point('validate')
builder.add_conditional_edges('validate', route_by_safety)
builder.add_edge('process', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'volume': 0.0,
    'safety_clearance': False,
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
