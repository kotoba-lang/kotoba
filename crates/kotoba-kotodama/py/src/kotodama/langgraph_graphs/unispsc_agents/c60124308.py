from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class KilnState(TypedDict):
    cone_type: str
    target_temp: float
    validation_passed: bool
    log: List[str]

def validate_cone(state: KilnState):
    print('Validating cone specifications...')
    passed = state['target_temp'] > 0
    return {'validation_passed': passed, 'log': ['Validation complete']}

def process_ordering(state: KilnState):
    print('Proceeding with procurement order based on cone specs.')
    return {'log': state['log'] + ['Order placed']}

graph = StateGraph(KilnState)
graph.add_node('validate', validate_cone)
graph.add_node('order', process_ordering)
graph.set_entry_point('validate')
graph.add_edge('validate', 'order')
graph.add_edge('order', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'cone_type': "",
    'target_temp': 0.0,
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
