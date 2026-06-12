from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class LiquidNitrogenState(TypedDict):
    purity_level: float
    container_pressure: float
    safety_clearance: bool
    log_entries: Annotated[Sequence[str], operator.add]

def validate_purity(state: LiquidNitrogenState):
    if state['purity_level'] < 99.999:
        return {'log_entries': ['Purity level insufficient for semiconductor grade']}
    return {'safety_clearance': True, 'log_entries': ['Purity verified']}

def check_container(state: LiquidNitrogenState):
    if state['container_pressure'] > 5.0:
        return {'safety_clearance': False, 'log_entries': ['High pressure alert - storage rejected']}
    return {'log_entries': ['Container integrity checked']}

def process_delivery(state: LiquidNitrogenState):
    if state.get('safety_clearance'):
        return {'log_entries': ['Delivery scheduled', 'Cryogenic handling protocol activated']}
    return {'log_entries': ['Delivery aborted']}

graph = StateGraph(LiquidNitrogenState)
graph.add_node('validate', validate_purity)
graph.add_node('inspect', check_container)
graph.add_node('dispatch', process_delivery)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', 'dispatch')
graph.add_edge('dispatch', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'container_pressure': 0.0,
    'safety_clearance': False,
    'log_entries': []
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
