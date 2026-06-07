from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    api_purity: float
    storage_temp: str
    gmp_verified: bool

def validate_purity(state: PharmState):
    assert state['api_purity'] >= 99.0, 'Purity below standard'
    return {'status': 'Purity Validated'}

def verify_gmp(state: PharmState):
    return {'status': 'GMP Certified' if state['gmp_verified'] else 'Rejected'}

graph = StateGraph(PharmState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('verify_gmp', verify_gmp)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'verify_gmp')
graph.add_edge('verify_gmp', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'api_purity': 0.0,
    'storage_temp': "",
    'gmp_verified': False
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
