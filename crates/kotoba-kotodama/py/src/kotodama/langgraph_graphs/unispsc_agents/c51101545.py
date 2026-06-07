from typing import TypedDict, Annotated, List
import operator
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    lot_number: str
    temperature_logs: List[float]
    is_compliant: bool
    next_action: str

def validate_cold_chain(state: ReagentState) -> ReagentState:
    compliant = all(temp <= 8.0 for temp in state['temperature_logs'])
    return {**state, 'is_compliant': compliant, 'next_action': 'release' if compliant else 'quarantine'}

def process_reagent(state: ReagentState) -> ReagentState:
    if state['is_compliant']:
        return {**state, 'next_action': 'ship'}
    return {**state, 'next_action': 'notify_qc'}

graph = StateGraph(ReagentState)
graph.add_node('validate', validate_cold_chain)
graph.add_node('process', process_reagent)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'lot_number': "",
    'temperature_logs': [],
    'is_compliant': False,
    'next_action': ""
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
