from typing import TypedDict
from langgraph.graph import StateGraph, END

class BearingSpecState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_dimension(state: BearingSpecState):
    data = state['spec_data']
    passed = 'tolerance' in data and data['tolerance'] < 0.005
    return {'validation_passed': passed, 'error_log': ['Tolerance too high'] if not passed else []}

def validate_material(state: BearingSpecState):
    data = state['spec_data']
    passed = 'hardness' in data and 58 <= data['hardness'] <= 65
    return {'validation_passed': state['validation_passed'] and passed}

graph = StateGraph(BearingSpecState)
graph.add_node('val_dim', validate_dimension)
graph.add_node('val_mat', validate_material)
graph.set_entry_point('val_dim')
graph.add_edge('val_dim', 'val_mat')
graph.add_edge('val_mat', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_passed': False,
    'error_log': []
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
