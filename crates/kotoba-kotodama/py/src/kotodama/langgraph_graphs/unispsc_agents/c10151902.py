from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class CommodityState(TypedDict):
    commodity_code: str
    quality_docs: List[str]
    validation_status: str
    risk_score: int

def validate_commodity(state: CommodityState):
    # Simulate inspection logic for agricultural raw materials
    return {'validation_status': 'passed' if len(state['quality_docs']) > 2 else 'failed'}

def assess_risk(state: CommodityState):
    return {'risk_score': 10 if state['validation_status'] == 'failed' else 2}

builder = StateGraph(CommodityState)
builder.add_node('validate', validate_commodity)
builder.add_node('risk', assess_risk)
builder.add_edge('validate', 'risk')
builder.add_edge('risk', END)
builder.set_entry_point('validate')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'quality_docs': [],
    'validation_status': "",
    'risk_score': 0
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
