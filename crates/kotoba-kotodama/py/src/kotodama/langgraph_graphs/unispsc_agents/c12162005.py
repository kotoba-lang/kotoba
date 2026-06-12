from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ResinState(TypedDict):
    material_id: str
    viscosity: float
    curing_temp: float
    validation_log: Annotated[Sequence[str], operator.add]
    status: str

def validate_viscosity(state: ResinState):
    if 500 <= state['viscosity'] <= 5000:
        return {'validation_log': ['Viscosity within range'], 'status': 'PROCESSING'}
    return {'validation_log': ['Viscosity deviation detected'], 'status': 'REJECTED'}

def process_curing(state: ResinState):
    if state['status'] == 'PROCESSING':
        if state['curing_temp'] < 150:
            return {'validation_log': ['Curing parameters approved'], 'status': 'APPROVED'}
        return {'validation_log': ['High-temp risk flagged'], 'status': 'REVIEW_REQUIRED'}
    return {'status': state['status']}

graph = StateGraph(ResinState)
graph.add_node('validate', validate_viscosity)
graph.add_node('cure', process_curing)
graph.set_entry_point('validate')
graph.add_edge('validate', 'cure')
graph.add_edge('cure', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'viscosity': 0.0,
    'curing_temp': 0.0,
    'validation_log': [],
    'status': ""
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
