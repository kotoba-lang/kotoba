from typing import TypedDict
from langgraph.graph import StateGraph, END

class HeaterSpecState(TypedDict):
    specs: dict
    validation_errors: list
    is_compliant: bool

def validate_heater_specs(state: HeaterSpecState):
    errors = []
    if state['specs'].get('wattage', 0) <= 0:
        errors.append('Invalid wattage')
    if not state['specs'].get('sheath_material'):
        errors.append('Missing material spec')
    return {'validation_errors': errors, 'is_compliant': len(errors) == 0}

def route_by_compliance(state: HeaterSpecState):
    return 'compliant_path' if state['is_compliant'] else 'reject_path'

graph = StateGraph(HeaterSpecState)
graph.add_node('validate', validate_heater_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance, {'compliant_path': END, 'reject_path': END})
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'validation_errors': [],
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
