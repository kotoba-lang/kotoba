from typing import TypedDict
from langgraph.graph import StateGraph, END

class TipState(TypedDict):
    brand: str
    volume_ul: float
    purity_level: str
    is_validated: bool

def validate_spec(state: TipState):
    if state['volume_ul'] < 0.1 or state['volume_ul'] > 20:
        return {'is_validated': False}
    return {'is_validated': True}

def check_purity(state: TipState):
    required_levels = ['RNase-free', 'DNase-free', 'Pyrogen-free']
    return {'is_validated': state['purity_level'] in required_levels}

graph = StateGraph(TipState)
graph.add_node('validate_spec', validate_spec)
graph.add_node('check_purity', check_purity)
graph.set_entry_point('validate_spec')
graph.add_edge('validate_spec', 'check_purity')
graph.add_edge('check_purity', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'brand': "",
    'volume_ul': 0.0,
    'purity_level': "",
    'is_validated': False
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
