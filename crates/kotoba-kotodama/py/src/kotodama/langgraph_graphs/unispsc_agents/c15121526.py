from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, END

class AlloySpecState(TypedDict):
    material_id: str
    spec_data: dict
    validation_log: List[str]
    is_compliant: bool

def validate_material(state: AlloySpecState):
    log = []
    compliant = True
    if 'tensile_strength' not in state['spec_data']:
        log.append('Missing tensile strength')
        compliant = False
    return {'validation_log': log, 'is_compliant': compliant}

def process_machining(state: AlloySpecState):
    return {'validation_log': state['validation_log'] + ['Machining route verified']}

graph = StateGraph(AlloySpecState)
graph.add_node('validate', validate_material)
graph.add_node('machining', process_machining)
graph.set_entry_point('validate')
graph.add_edge('validate', 'machining')
graph.add_edge('machining', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'spec_data': {},
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
