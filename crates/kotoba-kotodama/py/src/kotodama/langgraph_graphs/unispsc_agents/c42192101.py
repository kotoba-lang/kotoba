from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PhlebotomySpecState(TypedDict):
    item_id: str
    specs: dict
    approved: bool
    validation_log: List[str]

def validate_specs(state: PhlebotomySpecState):
    log = []
    if state['specs'].get('WeightCapacity', 0) < 150:
        log.append('Weight capacity insufficient for standard medical chair safety.')
    return {'validation_log': log, 'approved': len(log) == 0}

def graph_nodes():
    builder = StateGraph(PhlebotomySpecState)
    builder.add_node('validate', validate_specs)
    builder.set_entry_point('validate')
    builder.add_edge('validate', END)
    return builder.compile()

graph = graph_nodes()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'item_id': "",
    'specs': {},
    'approved': False,
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
