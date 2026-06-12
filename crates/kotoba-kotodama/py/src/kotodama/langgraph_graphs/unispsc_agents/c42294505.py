from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class OphthalmicState(TypedDict):
    part_id: str
    specifications: dict
    validation_results: List[str]

def validate_biocompatibility(state: OphthalmicState):
    if 'iso_10993' not in state['specifications'].get('certifications', []):
        return {'validation_results': ['Biocompatibility certification missing']}
    return {'validation_results': ['Biocompatibility verified']}

def check_dimensions(state: OphthalmicState):
    if 'dimensions' not in state['specifications']:
        return {'validation_results': state['validation_results'] + ['Missing dimensions']}
    return {'validation_results': state['validation_results'] + ['Dimensions validated']}

graph = StateGraph(OphthalmicState)
graph.add_node('validate_bio', validate_biocompatibility)
graph.add_node('check_dims', check_dimensions)
graph.set_entry_point('validate_bio')
graph.add_edge('validate_bio', 'check_dims')
graph.add_edge('check_dims', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'specifications': {},
    'validation_results': []
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
