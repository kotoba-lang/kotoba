from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CutbackState(TypedDict):
    product_specs: dict
    validation_passed: bool
    safety_check_logs: List[str]

def validate_flash_point(state: CutbackState):
    flash_point = state['product_specs'].get('flash_point', 0)
    if flash_point < 38:
        state['safety_check_logs'].append('Critical: Flash point below regulated safe threshold.')
        state['validation_passed'] = False
    return state

def check_voc_compliance(state: CutbackState):
    if 'voc_level' not in state['product_specs']:
        state['safety_check_logs'].append('Missing VOC compliance certificate.')
        state['validation_passed'] = False
    return state

graph = StateGraph(CutbackState)
graph.add_node('validate_flash', validate_flash_point)
graph.add_node('check_voc', check_voc_compliance)
graph.set_entry_point('validate_flash')
graph.add_edge('validate_flash', 'check_voc')
graph.add_edge('check_voc', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_specs': {},
    'validation_passed': False,
    'safety_check_logs': []
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
