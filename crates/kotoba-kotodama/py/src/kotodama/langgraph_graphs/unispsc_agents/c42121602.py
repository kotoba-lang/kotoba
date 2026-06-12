from typing import TypedDict
from langgraph.graph import StateGraph, END

class BloodProductState(TypedDict):
    batch_id: str
    temp_log: float
    gmp_verified: bool
    status: str

def validate_gmp(state: BloodProductState):
    state['gmp_verified'] = True
    return {'status': 'CERTIFIED' if state['gmp_verified'] else 'REJECTED'}

def check_temp(state: BloodProductState):
    return {'status': 'VALID' if 2.0 <= state['temp_log'] <= 8.0 else 'EXPIRED'}

graph = StateGraph(BloodProductState)
graph.add_node('verify', validate_gmp)
graph.add_node('check', check_temp)
graph.set_entry_point('verify')
graph.add_edge('verify', 'check')
graph.add_edge('check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'temp_log': 0.0,
    'gmp_verified': False,
    'status': ""
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
