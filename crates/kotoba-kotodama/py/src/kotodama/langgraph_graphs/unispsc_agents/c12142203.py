from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class WaferState(TypedDict):
    spec_id: str
    crystal_orientation: str
    resistivity: float
    inspection_result: bool
    validation_log: List[str]

def validate_crystal(state: WaferState) -> WaferState:
    if state['crystal_orientation'] not in ['100', '111']:
        state['validation_log'].append('Invalid orientation')
        state['inspection_result'] = False
    return state

def check_resistivity(state: WaferState) -> WaferState:
    if 1.0 <= state['resistivity'] <= 100.0:
        state['validation_log'].append('Resistivity in range')
    else:
        state['inspection_result'] = False
        state['validation_log'].append('Resistivity out of range')
    return state

graph = StateGraph(WaferState)
graph.add_node('validate_crystal', validate_crystal)
graph.add_node('check_resistivity', check_resistivity)
graph.set_entry_point('validate_crystal')
graph.add_edge('validate_crystal', 'check_resistivity')
graph.add_edge('check_resistivity', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_id': "",
    'crystal_orientation': "",
    'resistivity': 0.0,
    'inspection_result': False,
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
