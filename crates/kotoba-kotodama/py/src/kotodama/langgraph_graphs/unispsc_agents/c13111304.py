from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
import operator

class MineralState(TypedDict):
    commodity_code: str
    purity_check: bool
    lab_results: dict
    inspection_status: str
    log: Annotated[List[str], operator.add]

def validate_purity(state: MineralState):
    purity = state['lab_results'].get('purity', 0)
    is_valid = purity >= 95.0
    return {'purity_check': is_valid, 'inspection_status': 'passed' if is_valid else 'rejected', 'log': ['Purity validation completed']}

def route_by_purity(state: MineralState):
    return 'check_composition' if state['purity_check'] else END

def check_composition(state: MineralState):
    return {'inspection_status': 'verified', 'log': ['Chemical composition analysis completed']}

graph = StateGraph(MineralState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_composition', check_composition)
graph.set_entry_point('validate_purity')
graph.add_conditional_edges('validate_purity', route_by_purity)
graph.add_edge('check_composition', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'purity_check': False,
    'lab_results': {},
    'inspection_status': "",
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
