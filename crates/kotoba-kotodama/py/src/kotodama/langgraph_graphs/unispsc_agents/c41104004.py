from typing import TypedDict
from langgraph.graph import StateGraph, END

class PrepBombState(TypedDict):
    spec_sheet: dict
    validation_results: list
    is_compliant: bool

def validate_pressure_rating(state: PrepBombState):
    """Checks if the specified pressure rating meets safety standards."""
    rating = state['spec_sheet'].get('max_pressure_rating_mpa', 0)
    valid = rating > 0
    return {'validation_results': [f'Pressure rating validation: {valid}'], 'is_compliant': valid}

def compile_graph():
    workflow = StateGraph(PrepBombState)
    workflow.add_node('validate', validate_pressure_rating)
    workflow.set_entry_point('validate')
    workflow.add_edge('validate', END)
    return workflow.compile()

graph = compile_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_sheet': {},
    'validation_results': [],
    'is_compliant': False
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
