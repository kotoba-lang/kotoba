from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class RubberState(TypedDict):
    requirements: dict
    validation_errors: List[str]
    is_approved: bool

def validate_rubber_specs(state: RubberState):
    errors = []
    if state['requirements'].get('durometer_hardness', 0) < 30:
        errors.append('Hardness value too low for structural integrity.')
    return {'validation_errors': errors, 'is_approved': len(errors) == 0}

def check_thermal_tolerance(state: RubberState):
    if state['requirements'].get('temp_celsius', 0) > 150:
        return {'is_approved': True}
    return {'is_approved': False}

graph = StateGraph(RubberState)
graph.add_node('validate', validate_rubber_specs)
graph.add_node('thermal_check', check_thermal_tolerance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'thermal_check')
graph.add_edge('thermal_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'requirements': {},
    'validation_errors': [],
    'is_approved': False
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
