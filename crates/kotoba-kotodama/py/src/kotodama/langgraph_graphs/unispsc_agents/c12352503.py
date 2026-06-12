from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ResinProcessingState(TypedDict):
    resin_id: str
    viscosity: float
    curing_temp: float
    validation_passed: bool
    log: Annotated[Sequence[str], add_messages]

def validate_viscosity(state: ResinProcessingState):
    if 500 <= state['viscosity'] <= 2000:
        return {'validation_passed': True, 'log': ['Viscosity validated']}
    return {'validation_passed': False, 'log': ['Viscosity out of spec']}

def route_by_validation(state: ResinProcessingState):
    return 'process' if state['validation_passed'] else END

def process_resin(state: ResinProcessingState):
    return {'log': [f'Processing at {state['curing_temp']}C']}

graph = StateGraph(ResinProcessingState)
graph.add_node('validate', validate_viscosity)
graph.add_node('process', process_resin)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation, {'process': 'process', '__end__': END})
graph.add_edge('process', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'resin_id': "",
    'viscosity': 0.0,
    'curing_temp': 0.0,
    'validation_passed': False,
    'log': []
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
