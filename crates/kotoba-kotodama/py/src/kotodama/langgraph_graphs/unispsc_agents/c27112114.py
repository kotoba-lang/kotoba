from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolSpecState(TypedDict):
    tool_name: str
    hrc_rating: int
    is_insulated: bool
    validation_status: str

def validate_hardness(state: ToolSpecState):
    if state['hrc_rating'] < 55:
        return {'validation_status': 'REJECTED: Below required hardness'}
    return {'validation_status': 'PASSED'}

def check_insulation(state: ToolSpecState):
    if state['is_insulated']:
        return {'validation_status': 'PASSED: VDE Certified'}
    return {'validation_status': 'PASSED: Standard Industrial'}

graph = StateGraph(ToolSpecState)
graph.add_node('hardness_check', validate_hardness)
graph.add_node('insulation_check', check_insulation)
graph.set_entry_point('hardness_check')
graph.add_edge('hardness_check', 'insulation_check')
graph.add_edge('insulation_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'tool_name': "",
    'hrc_rating': 0,
    'is_insulated': False,
    'validation_status': ""
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
