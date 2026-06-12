from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class CommodityState(TypedDict):
    commodity_id: str
    spec_data: dict
    validation_log: Annotated[List[str], operator.add]
    is_approved: bool

def validate_origin(state: CommodityState):
    origin = state['spec_data'].get('origin_country')
    if origin:
        return {'validation_log': [f'Origin {origin} verified.']}
    return {'validation_log': ['Origin missing.']}

def check_certification(state: CommodityState):
    cert = state['spec_data'].get('certification_standard')
    status = True if cert else False
    return {'is_approved': status, 'validation_log': [f'Certification check: {status}']}

graph = StateGraph(CommodityState)
graph.add_node('validate_origin', validate_origin)
graph.add_node('check_certification', check_certification)
graph.set_entry_point('validate_origin')
graph.add_edge('validate_origin', 'check_certification')
graph.add_edge('check_certification', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_id': "",
    'spec_data': {},
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
