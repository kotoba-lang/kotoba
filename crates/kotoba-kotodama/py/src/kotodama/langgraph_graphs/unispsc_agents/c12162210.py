from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class FluorineState(TypedDict):
    purity_level: float
    safety_clearance: bool
    log: Annotated[Sequence[str], operator.add]

def validate_purity(state: FluorineState) -> FluorineState:
    if state['purity_level'] < 99.999:
        return {'log': ['Purity check failed: Below 5N threshold.']}
    return {'log': ['Purity validated successfully.']}

def safety_routing(state: FluorineState) -> str:
    return 'safe' if state['safety_clearance'] else 'halt'

def process_shipment(state: FluorineState) -> FluorineState:
    return {'log': ['Processing hazardous material shipment protocols.']}

def halt_process(state: FluorineState) -> FluorineState:
    return {'log': ['ABORT: High-purity fluorine safety violation.']}

graph = StateGraph(FluorineState)
graph.add_node('validate', validate_purity)
graph.add_node('process', process_shipment)
graph.add_node('halt', halt_process)
graph.add_edge('validate', 'process')
graph.add_conditional_edges('validate', safety_routing, {'safe': 'process', 'halt': 'halt'})
graph.add_edge('process', END)
graph.add_edge('halt', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'safety_clearance': False,
    'log': []
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
