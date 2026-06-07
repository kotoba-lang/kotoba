from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MiningState(TypedDict):
    props_id: str
    load_bearing_capacity: float
    inspection_result: bool
    is_safe: bool

def validate_load(state: MiningState) -> MiningState:
    # Logic to ensure the prop meets minimum load-bearing requirements for safety
    state['is_safe'] = state['load_bearing_capacity'] >= 50.0
    return state

def approve_prop(state: MiningState) -> MiningState:
    state['inspection_result'] = True
    return state

graph = StateGraph(MiningState)
graph.add_node('validate_load', validate_load)
graph.add_node('approve_prop', approve_prop)
graph.set_entry_point('validate_load')
graph.add_edge('validate_load', 'approve_prop')
graph.add_edge('approve_prop', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'props_id': "",
    'load_bearing_capacity': 0.0,
    'inspection_result': False,
    'is_safe': False
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
