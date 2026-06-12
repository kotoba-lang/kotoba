from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class CopperOrder(TypedDict):
    specs: dict
    validation_passed: bool
    error_log: List[str]

def validate_dimensions(state: CopperOrder):
    specs = state['specs']
    passed = specs.get('tolerance', 0.1) <= 0.05
    return {'validation_passed': passed, 'error_log': [] if passed else ['Tolerance out of spec']}

def process_stamping(state: CopperOrder):
    print('Initiating industrial stamping qualification workflow...')
    return {'validation_passed': True}

graph = StateGraph(CopperOrder)
graph.add_node('validate', validate_dimensions)
graph.add_node('stamp_process', process_stamping)
graph.set_entry_point('validate')
graph.add_edge('validate', 'stamp_process')
graph.add_edge('stamp_process', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
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
