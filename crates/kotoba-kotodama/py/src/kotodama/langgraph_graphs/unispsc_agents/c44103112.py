from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict

class RibbonState(TypedDict):
    model_number: str
    is_compatible: bool
    validation_log: str

def validate_compatibility(state: RibbonState):
    # Business logic for ink ribbon compatibility check
    valid_models = ['EPSON-LQ-590', 'OKI-ML-8490']
    result = state['model_number'] in valid_models
    return {'is_compatible': result, 'validation_log': 'Compatibility confirmed' if result else 'Not compatible'}

def route_by_compatibility(state: RibbonState):
    return 'process' if state['is_compatible'] else END

graph = StateGraph(RibbonState)
graph.add_node('validate', validate_compatibility)
graph.add_node('process', lambda x: {'validation_log': 'Proceeding to procurement'})
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compatibility)
graph.add_edge('process', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'model_number': "",
    'is_compatible': False,
    'validation_log': ""
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
