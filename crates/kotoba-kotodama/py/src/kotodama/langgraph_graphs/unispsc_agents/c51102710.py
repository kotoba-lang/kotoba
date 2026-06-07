from typing import TypedDict
from langgraph.graph import StateGraph, END

class AntisepticState(TypedDict):
    product_name: str
    concentration: float
    is_flammable: bool
    validation_passed: bool

def validate_composition(state: AntisepticState):
    # Validate ethanol/acetone concentration matches regulatory standards
    state['validation_passed'] = 60.0 <= state['concentration'] <= 95.0
    return state

def check_hazard_compliance(state: AntisepticState):
    # Ensure dangerous goods documentation exists for high-risk items
    if state['is_flammable']:
        print('Hazard verification: Flammable goods protocols active.')
    return state

graph = StateGraph(AntisepticState)
graph.add_node('composition', validate_composition)
graph.add_node('safety', check_hazard_compliance)
graph.set_entry_point('composition')
graph.add_edge('composition', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_name': "",
    'concentration': 0.0,
    'is_flammable': False,
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
