from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PrintingState(TypedDict):
    material_id: str
    quality_checks: List[str]
    approved: bool

def validate_media_specs(state: PrintingState):
    # Simulated validation logic for paper specs
    state['quality_checks'].append('spec_validated')
    return state

def verify_printer_compatibility(state: PrintingState):
    # Logic to ensure media aligns with machine constraints
    state['quality_checks'].append('compatibility_verified')
    state['approved'] = True
    return state

graph = StateGraph(PrintingState)
graph.add_node('validate_specs', validate_media_specs)
graph.add_node('verify_compatibility', verify_printer_compatibility)
graph.add_edge('validate_specs', 'verify_compatibility')
graph.add_edge('verify_compatibility', END)
graph.set_entry_point('validate_specs')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'quality_checks': [],
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
