from typing import TypedDict
from langgraph.graph import StateGraph, END

class StoveState(TypedDict):
    fuel_type: str
    safety_check_passed: bool
    validation_log: list

def validate_fuel(state: StoveState):
    valid = state['fuel_type'] in ['isobutane', 'propane', 'white_gas']
    return {'safety_check_passed': valid, 'validation_log': ['Fuel verified' if valid else 'Fuel invalid']}

def finalize_procurement(state: StoveState):
    return {'validation_log': state['validation_log'] + ['Procurement approved']}

graph = StateGraph(StoveState)
graph.add_node('fuel_check', validate_fuel)
graph.add_node('finalizer', finalize_procurement)
graph.add_edge('fuel_check', 'finalizer')
graph.add_edge('finalizer', END)
graph.set_entry_point('fuel_check')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'fuel_type': "",
    'safety_check_passed': False,
    'validation_log': []
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
