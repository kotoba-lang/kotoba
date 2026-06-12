from typing import TypedDict
from langgraph.graph import StateGraph, END

class RespiratorState(TypedDict):
    model_number: str
    certification_body: str
    filtration_efficiency: float
    verified: bool

def validate_respirator_specs(state: RespiratorState):
    # Business logic for validation
    is_valid = state['filtration_efficiency'] >= 95.0 and state['certification_body'] in ['NIOSH', 'JIS', 'EN']
    return {'verified': is_valid}

graph_builder = StateGraph(RespiratorState)
graph_builder.add_node('validate', validate_respirator_specs)
graph_builder.set_entry_point('validate')
graph_builder.add_edge('validate', END)
graph = graph_builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'model_number': "",
    'certification_body': "",
    'filtration_efficiency': 0.0,
    'verified': False
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
