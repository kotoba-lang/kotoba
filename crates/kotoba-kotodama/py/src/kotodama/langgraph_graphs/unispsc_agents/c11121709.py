from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class OilProcurementState(TypedDict):
    commodity_code: str
    specifications: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_purity(state: OilProcurementState):
    purity = state['specifications'].get('purity_percentage', 0)
    if purity >= 99.0:
        return {'validation_log': ['Purity level acceptable'], 'is_compliant': True}
    return {'validation_log': ['Purity too low'], 'is_compliant': False}

def safety_check(state: OilProcurementState):
    flash_point = state['specifications'].get('flash_point_celsius', 0)
    if flash_point > 100:
        return {'validation_log': ['Safety standards met']}
    return {'validation_log': ['High risk: Flash point below threshold']}

graph = StateGraph(OilProcurementState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('safety_check', safety_check)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'safety_check')
graph.add_edge('safety_check', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'specifications': {},
    'validation_log': [],
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
