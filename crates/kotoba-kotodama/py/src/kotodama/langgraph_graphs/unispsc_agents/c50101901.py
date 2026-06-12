from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SupplyState(TypedDict):
    commodity: str
    quality_passed: bool
    temp_log: List[float]
    status: str

def validate_freshness(state: SupplyState):
    avg_temp = sum(state['temp_log']) / len(state['temp_log']) if state['temp_log'] else 10.0
    return {'quality_passed': avg_temp < 4.0, 'status': 'VALIDATED' if avg_temp < 4.0 else 'REJECTED'}

def process_shipment(state: SupplyState):
    return {'status': 'READY_FOR_DISTRIBUTION' if state['quality_passed'] else 'DISCARD'}

graph = StateGraph(SupplyState)
graph.add_node('validate', validate_freshness)
graph.add_node('process', process_shipment)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity': "",
    'quality_passed': False,
    'temp_log': [],
    'status': ""
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
