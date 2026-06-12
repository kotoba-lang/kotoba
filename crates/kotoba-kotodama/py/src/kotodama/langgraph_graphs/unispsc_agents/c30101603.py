from typing import TypedDict
from langgraph.graph import StateGraph, END

class IronBarState(TypedDict):
    spec_data: dict
    validated: bool
    error: str

def validate_specs(state: IronBarState):
    specs = state['spec_data']
    required_keys = ['material_grade', 'diameter', 'tensile_strength']
    all_present = all(k in specs for k in required_keys)
    return {'validated': all_present, 'error': '' if all_present else 'Missing requirements'}

def structural_integrity_check(state: IronBarState):
    if state.get('validated'):
        print('Performing integrity validation...')
    return state

graph = StateGraph(IronBarState)
graph.add_node('validate', validate_specs)
graph.add_node('integrity', structural_integrity_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'integrity')
graph.add_edge('integrity', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validated': False,
    'error': ""
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
