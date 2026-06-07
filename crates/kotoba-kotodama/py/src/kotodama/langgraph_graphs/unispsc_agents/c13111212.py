from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, END
import operator

class DrillBitState(TypedDict):
    bit_id: str
    specs: dict
    validation_log: Annotated[List[str], operator.add]
    is_approved: bool

def validate_bit_hardness(state: DrillBitState) -> DrillBitState:
    hardness = state['specs'].get('hardness', 0)
    if hardness >= 9.5:
        state['validation_log'] = ['Hardness validated as industrial grade.']
    else:
        state['validation_log'] = ['Hardness below threshold.']
    return state

def check_thermal_rating(state: DrillBitState) -> DrillBitState:
    rating = state['specs'].get('thermal_stability', 0)
    if rating > 800:
        state['validation_log'] = ['Thermal stability verified.']
        state['is_approved'] = True
    else:
        state['is_approved'] = False
    return state

graph = StateGraph(DrillBitState)
graph.add_node('validate_hardness', validate_bit_hardness)
graph.add_node('check_thermal', check_thermal_rating)
graph.set_entry_point('validate_hardness')
graph.add_edge('validate_hardness', 'check_thermal')
graph.add_edge('check_thermal', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'bit_id': "",
    'specs': {},
    'validation_log': [],
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
