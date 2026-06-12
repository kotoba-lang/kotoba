from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SiCState(TypedDict):
    purity: float
    particle_size: float
    export_cleared: bool
    validation_log: List[str]

def validate_purity(state: SiCState) -> dict:
    purity = state.get('purity', 0)
    if purity >= 99.9:
        return {'validation_log': state['validation_log'] + ['Purity verified: High Grade']}
    return {'validation_log': state['validation_log'] + ['Purity below threshold']}

def check_export_control(state: SiCState) -> dict:
    if state.get('export_cleared'):
        return {'validation_log': state['validation_log'] + ['Export control cleared']}
    return {'validation_log': state['validation_log'] + ['Export control required']}

graph = StateGraph(SiCState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_export_control', check_export_control)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_export_control')
graph.add_edge('check_export_control', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'particle_size': 0.0,
    'export_cleared': False,
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
