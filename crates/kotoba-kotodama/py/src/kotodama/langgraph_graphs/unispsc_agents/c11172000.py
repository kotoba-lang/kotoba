from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class CommodityState(TypedDict):
    commodity_id: str
    purity: float
    validation_logs: Annotated[List[str], operator.add]
    is_compliant: bool

def validate_purity(state: CommodityState):
    if state['purity'] >= 99.9:
        return {'validation_logs': ['Purity check passed: High-grade'], 'is_compliant': True}
    return {'validation_logs': ['Purity check failed: Below threshold'], 'is_compliant': False}

def security_protocol(state: CommodityState):
    if state['is_compliant']:
        return {'validation_logs': ['Security screening completed: Approved for procurement']}
    return {'validation_logs': ['Security screening failed: Manual review required']}

graph = StateGraph(CommodityState)
graph.add_node('purity_check', validate_purity)
graph.add_node('security_check', security_protocol)
graph.set_entry_point('purity_check')
graph.add_edge('purity_check', 'security_check')
graph.add_edge('security_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_id': "",
    'purity': 0.0,
    'validation_logs': [],
    'is_compliant': False
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
