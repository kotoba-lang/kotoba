from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class StationeryState(TypedDict):
    item_code: str
    quantity: int
    is_compliant: bool
    inspection_report: List[str]

def validate_supply(state: StationeryState):
    report = []
    compliant = True
    if state['quantity'] <= 0:
        report.append('Invalid quantity')
        compliant = False
    return {'is_compliant': compliant, 'inspection_report': report}

def process_procurement(state: StationeryState):
    return {'inspection_report': state['inspection_report'] + ['Supply chain verified']}

graph = StateGraph(StationeryState)
graph.add_node('validate', validate_supply)
graph.add_node('procure', process_procurement)
graph.add_edge('validate', 'procure')
graph.add_edge('procure', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'item_code': "",
    'quantity': 0,
    'is_compliant': False,
    'inspection_report': []
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
