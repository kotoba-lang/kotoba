from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class RollerBottleState(TypedDict):
    bottle_spec: dict
    validation_passed: bool
    log: List[str]

def validate_sterility(state: RollerBottleState):
    sal = state['bottle_spec'].get('sal', 0)
    passed = sal >= 6
    return {'validation_passed': passed, 'log': [f'Sterility check: {passed}']}

def check_dimensions(state: RollerBottleState):
    dim = state['bottle_spec'].get('dimensions', {})
    passed = all(k in dim for k in ['diameter', 'length'])
    return {'validation_passed': passed, 'log': ['Dimension check completed']}

graph = StateGraph(RollerBottleState)
graph.add_node('validate_sterility', validate_sterility)
graph.add_node('check_dimensions', check_dimensions)
graph.set_entry_point('validate_sterility')
graph.add_edge('validate_sterility', 'check_dimensions')
graph.add_edge('check_dimensions', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'bottle_spec': {},
    'validation_passed': False,
    'log': []
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
