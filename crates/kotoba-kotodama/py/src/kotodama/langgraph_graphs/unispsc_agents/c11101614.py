from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, END

class ChemicalProcessState(TypedDict):
    batch_id: str
    purity_level: float
    safety_check_passed: bool
    process_logs: List[str]

def validate_purity(state: ChemicalProcessState) -> ChemicalProcessState:
    if state['purity_level'] < 99.9:
        state['process_logs'].append('Purity check failed')
        state['safety_check_passed'] = False
    else:
        state['process_logs'].append('Purity verified')
    return state

def logistics_handler(state: ChemicalProcessState) -> ChemicalProcessState:
    if state['safety_check_passed']:
        state['process_logs'].append('Logistics approved for hazardous materials')
    return state

graph = StateGraph(ChemicalProcessState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('logistics_handler', logistics_handler)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'logistics_handler')
graph.add_edge('logistics_handler', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'purity_level': 0.0,
    'safety_check_passed': False,
    'process_logs': []
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
