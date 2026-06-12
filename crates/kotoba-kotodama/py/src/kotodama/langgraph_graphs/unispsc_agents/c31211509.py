from typing import TypedDict
from langgraph.graph import StateGraph, END

class PrimerState(TypedDict):
    voc_content: float
    flash_point: float
    compliance_ok: bool

def validate_chemistry(state: PrimerState):
    if state['voc_content'] > 250:
        state['compliance_ok'] = False
    return state

def validate_safety(state: PrimerState):
    if state['flash_point'] < 30:
        state['compliance_ok'] = False
    return state

graph = StateGraph(PrimerState)
graph.add_node('chemistry_check', validate_chemistry)
graph.add_node('safety_check', validate_safety)
graph.set_entry_point('chemistry_check')
graph.add_edge('chemistry_check', 'safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'voc_content': 0.0,
    'flash_point': 0.0,
    'compliance_ok': False
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
