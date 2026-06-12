from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class FilingState(TypedDict):
    document_metadata: dict
    storage_requirements: list[str]
    validation_log: Annotated[list[str], operator.add]

def validate_materials(state: FilingState) -> FilingState:
    material = state['document_metadata'].get('material', 'unknown')
    status = 'Pass' if material in ['plastic', 'recycled_paper'] else 'Fail'
    return {'validation_log': [f'Material validation: {status} for {material}']}

def check_capacity(state: FilingState) -> FilingState:
    capacity = state['document_metadata'].get('capacity_sheets', 0)
    if capacity > 500:
        return {'validation_log': ['Capacity Warning: Exceeds standard binder limit']}
    return {'validation_log': ['Capacity: Within standard range']}

def build_graph():
    graph = StateGraph(FilingState)
    graph.add_node('validate_materials', validate_materials)
    graph.add_node('check_capacity', check_capacity)
    graph.set_entry_point('validate_materials')
    graph.add_edge('validate_materials', 'check_capacity')
    graph.add_edge('check_capacity', END)
    return graph.compile()

graph = build_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'document_metadata': {},
    'storage_requirements': [],
    'validation_log': []
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
