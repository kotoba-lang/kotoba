from typing import TypedDict
from langgraph.graph import StateGraph, END

class ContentSwitchState(TypedDict):
    model_id: str
    throughput_check: bool
    config_validated: bool

func_validate_throughput = lambda state: {'throughput_check': True} if '10g' in state['model_id'] else {'throughput_check': False}
func_validate_config = lambda state: {'config_validated': True}

graph = StateGraph(ContentSwitchState)
graph.add_node('throughput_analysis', func_validate_throughput)
graph.add_node('config_validation', func_validate_config)
graph.set_entry_point('throughput_analysis')
graph.add_edge('throughput_analysis', 'config_validation')
graph.add_edge('config_validation', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'model_id': "",
    'throughput_check': False,
    'config_validated': False
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
