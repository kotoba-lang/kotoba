from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CompostProcessingState(TypedDict):
    commodity_code: str
    material_type: str
    quality_metrics: dict
    validation_log: List[str]
    is_approved: bool

def validate_material_safety(state: CompostProcessingState) -> CompostProcessingState:
    metrics = state.get('quality_metrics', {})
    heavy_metals = metrics.get('heavy_metals', 0)
    state['is_approved'] = heavy_metals < 50
    state['validation_log'].append(f'Safety check passed: {state['is_approved']}')
    return state

def process_procurement(state: CompostProcessingState) -> CompostProcessingState:
    state['validation_log'].append('Procurement processed for compost distribution')
    return state

def create_compost_graph():
    workflow = StateGraph(CompostProcessingState)
    workflow.add_node('safety_check', validate_material_safety)
    workflow.add_node('process', process_procurement)
    workflow.set_entry_point('safety_check')
    workflow.add_edge('safety_check', 'process')
    workflow.add_edge('process', END)
    return workflow.compile()

graph = create_compost_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'material_type': "",
    'quality_metrics': {},
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
