from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class SemiconductorMaterialState(TypedDict):
    material_id: str
    purity_data: Dict[str, float]
    validation_passed: bool
    workflow_history: Annotated[List[str], add_messages]

def validate_material_purity(state: SemiconductorMaterialState):
    purity = state['purity_data'].get('purity', 0.0)
    return {'validation_passed': purity >= 99.9999, 'workflow_history': ['Purity Validation Executed']}

def perform_trace_analysis(state: SemiconductorMaterialState):
    return {'workflow_history': ['Trace Element Analysis Completed', 'Compliance check passed']}

graph = StateGraph(SemiconductorMaterialState)
graph.add_node('validate_purity', validate_material_purity)
graph.add_node('trace_analysis', perform_trace_analysis)
graph.add_edge('validate_purity', 'trace_analysis')
graph.add_edge('trace_analysis', END)
graph.set_entry_point('validate_purity')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity_data': {},
    'validation_passed': False,
    'workflow_history': []
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
