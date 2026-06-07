from typing import TypedDict
from langgraph.graph import StateGraph, END

class DeskingPartsState(TypedDict):
    part_id: str
    specs: dict
    validation_passed: bool

def validate_specs(state: DeskingPartsState):
    # Business logic for checking structural and ergonomic specifications
    is_valid = all(key in state['specs'] for key in ['load_limit', 'material', 'dimensions'])
    print(f'Validating parts for ID: {state['part_id']}')
    return {'validation_passed': is_valid}

def process_procurement(state: DeskingPartsState):
    if state['validation_passed']:
        print('Procurement request moving to supplier submission.')
    else:
        print('Specifications incomplete, triggering request for clarification.')
    return {}

graph = StateGraph(DeskingPartsState)
graph.add_node('validate', validate_specs)
graph.add_node('submit', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'submit')
graph.add_edge('submit', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'specs': {},
    'validation_passed': False
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
