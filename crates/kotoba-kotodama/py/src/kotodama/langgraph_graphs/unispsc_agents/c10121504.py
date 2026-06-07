from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class GrainProcurementState(TypedDict):
    commodity_code: str
    quality_metrics: dict
    approved: bool
    history: Annotated[List[str], list.append]

def validate_grain_quality(state: GrainProcurementState):
    metrics = state.get('quality_metrics', {})
    is_valid = metrics.get('moisture', 0) < 14.0 and metrics.get('impurities', 0) < 1.0
    return {'approved': is_valid, 'history': ['Validated moisture and impurities']}

def update_procurement_log(state: GrainProcurementState):
    return {'history': ['Logged quality validation result']}

builder = StateGraph(GrainProcurementState)
builder.add_node('validate', validate_grain_quality)
builder.add_node('log', update_procurement_log)
builder.add_edge('validate', 'log')
builder.add_edge('log', END)
builder.set_entry_point('validate')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'quality_metrics': {},
    'approved': False,
    'history': []
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
