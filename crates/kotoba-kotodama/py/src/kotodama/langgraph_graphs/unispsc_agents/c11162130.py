from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class BlastingState(TypedDict):
    material_spec: dict
    safety_clearance: bool
    transit_logs: Annotated[Sequence[str], operator.add]

def validate_materials(state: BlastingState):
    spec = state['material_spec']
    is_safe = all(k in spec for k in ['UN_number', 'detonation_velocity'])
    return {'safety_clearance': is_safe}

def process_logistics(state: BlastingState):
    if state['safety_clearance']:
        return {'transit_logs': ['Clearance confirmed', 'Transport protocol activated']}
    return {'transit_logs': ['Clearance failed - halt']}

graph = StateGraph(BlastingState)
graph.add_node('validate', validate_materials)
graph.add_node('logistics', process_logistics)
graph.set_entry_point('validate')
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_spec': {},
    'safety_clearance': False,
    'transit_logs': []
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
