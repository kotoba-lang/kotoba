from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    lot_number: str
    quality_passed: bool
    temperature_logs: List[float]
    final_status: str

def validate_quality(state: ReagentState) -> ReagentState:
    # Logic to verify quality check pass
    state['quality_passed'] = True
    return state

def check_temp_stability(state: ReagentState) -> ReagentState:
    # Logic to evaluate temperature stability logs
    if all(t < 8.0 for t in state['temperature_logs']):
        state['final_status'] = 'STABLE'
    else:
        state['final_status'] = 'EXPIRED'
    return state

graph = StateGraph(ReagentState)
graph.add_node('validate', validate_quality)
graph.add_node('check_temp', check_temp_stability)
graph.add_edge('validate', 'check_temp')
graph.add_edge('check_temp', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'lot_number': "",
    'quality_passed': False,
    'temperature_logs': [],
    'final_status': ""
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
