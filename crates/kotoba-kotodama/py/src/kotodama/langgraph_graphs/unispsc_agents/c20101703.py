from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class HydraulicState(TypedDict):
    pressure_req: float
    stroke_len: float
    validation_log: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_specs(state: HydraulicState):
    log = []
    if state['pressure_req'] > 70.0:
        log.append('High pressure requirement detected, requires reinforced seals.')
    if state['stroke_len'] <= 0:
        raise ValueError('Invalid stroke length')
    return {'validation_log': log, 'is_compliant': True}

def process_procurement(state: HydraulicState):
    return {'validation_log': ['Procurement order drafted for hydraulic actuator.']}

graph = StateGraph(HydraulicState)
graph.add_node('validate', validate_specs)
graph.add_node('procure', process_procurement)
graph.add_edge('validate', 'procure')
graph.add_edge('procure', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'pressure_req': 0.0,
    'stroke_len': 0.0,
    'validation_log': [],
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
