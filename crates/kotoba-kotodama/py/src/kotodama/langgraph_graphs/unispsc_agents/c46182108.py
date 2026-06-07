from typing import TypedDict
from langgraph.graph import StateGraph, END

class AntistaticSpecState(TypedDict):
    resistance: float
    compliance_cert: str
    is_valid: bool

def validate_resistance(state: AntistaticSpecState):
    # Industry standard for ESD straps is typically 10^5 to 10^9 ohms
    state['is_valid'] = 1e5 <= state['resistance'] <= 1e9
    return state

def check_compliance(state: AntistaticSpecState):
    state['is_valid'] = bool(state['compliance_cert'] == 'ESD S20.20')
    return state

graph = StateGraph(AntistaticSpecState)
graph.add_node('val_res', validate_resistance)
graph.add_node('val_cert', check_compliance)
graph.set_entry_point('val_res')
graph.add_edge('val_res', 'val_cert')
graph.add_edge('val_cert', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'resistance': 0.0,
    'compliance_cert': "",
    'is_valid': False
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
