from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MountState(TypedDict):
    mount_specs: dict
    validation_passed: bool
    log: List[str]

def validate_specs(state: MountState):
    specs = state['mount_specs']
    passed = 'pull_force_kg' in specs and specs['pull_force_kg'] > 0
    return {'validation_passed': passed, 'log': [f'Validation result: {passed}']}

def finalize_order(state: MountState):
    return {'log': state['log'] + ['Order ready for procurement approval']}

graph_builder = StateGraph(MountState)
graph_builder.add_node('validate', validate_specs)
graph_builder.add_node('finalize', finalize_order)
graph_builder.set_entry_point('validate')
graph_builder.add_edge('validate', 'finalize')
graph_builder.add_edge('finalize', END)
graph = graph_builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'mount_specs': {},
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
