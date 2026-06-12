from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class BoltState(TypedDict):
    bolt_id: str
    spec_compliance: bool
    inspection_results: List[str]
    approved: bool

def validate_material(state: BoltState):
    # Simulate material validation logic
    state['inspection_results'].append('Material grade verified')
    return {'spec_compliance': True}

def perform_quality_check(state: BoltState):
    # Simulate QC logic
    state['inspection_results'].append('Dimensional tolerance check passed')
    return {'approved': True}

graph = StateGraph(BoltState)
graph.add_node('validate_material', validate_material)
graph.add_node('perform_quality_check', perform_quality_check)
graph.add_edge('validate_material', 'perform_quality_check')
graph.add_edge('perform_quality_check', END)
graph.set_entry_point('validate_material')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'bolt_id': "",
    'spec_compliance': False,
    'inspection_results': [],
    'approved': False
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
