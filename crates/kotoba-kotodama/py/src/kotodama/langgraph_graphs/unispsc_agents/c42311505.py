from typing import TypedDict
from langgraph.graph import StateGraph, END

class BandageState(TypedDict):
    specs: dict
    is_compliant: bool
    validation_log: list

def validate_sterility(state: BandageState):
    is_sterile = state['specs'].get('sterility_cert') is not None
    return {'is_compliant': is_sterile, 'validation_log': ['Sterility check passed'] if is_sterile else ['Sterility cert missing']}

def check_expiry(state: BandageState):
    expiry = state['specs'].get('expiry_date')
    return {'validation_log': state['validation_log'] + ['Expiry date verified']}

graph = StateGraph(BandageState)
graph.add_node('validate', validate_sterility)
graph.add_node('expiry', check_expiry)
graph.add_edge('validate', 'expiry')
graph.add_edge('expiry', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'is_compliant': False,
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
