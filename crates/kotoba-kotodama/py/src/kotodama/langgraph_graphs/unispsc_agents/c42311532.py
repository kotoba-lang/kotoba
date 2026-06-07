from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class DressingState(TypedDict):
    spec_data: dict
    validation_errors: List[str]
    approved: bool

def validate_sterility(state: DressingState):
    """Ensures the dressing meets medical sterile standards."""
    if 'sterilization_method' not in state['spec_data']:
        state['validation_errors'].append('Missing sterilization data')
    return state

def check_regulatory(state: DressingState):
    """Checks compliance with health authority certifications."""
    if 'iso_cert' not in state['spec_data']:
        state['validation_errors'].append('Missing ISO 13485 certification')
    return state

graph = StateGraph(DressingState)
graph.add_node('sterility', validate_sterility)
graph.add_node('regulatory', check_regulatory)
graph.set_entry_point('sterility')
graph.add_edge('sterility', 'regulatory')
graph.add_edge('regulatory', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_errors': [],
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
