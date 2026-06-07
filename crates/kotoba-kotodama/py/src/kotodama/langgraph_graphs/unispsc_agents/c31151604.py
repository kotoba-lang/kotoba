from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ChainState(TypedDict):
    load_requirement: float
    safety_factor: int
    cert_provided: bool
    is_approved: bool

def validate_load(state: ChainState) -> ChainState:
    if state['load_requirement'] > 0 and state['safety_factor'] >= 4:
        state['is_approved'] = True
    return state

def check_certification(state: ChainState) -> ChainState:
    if not state.get('cert_provided', False):
        state['is_approved'] = False
    return state

graph = StateGraph(ChainState)
graph.add_node("validate", validate_load)
graph.add_node("certify", check_certification)
graph.set_entry_point("validate")
graph.add_edge("validate", "certify")
graph.add_edge("certify", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'load_requirement': 0.0,
    'safety_factor': 0,
    'cert_provided': False,
    'is_approved': False
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
