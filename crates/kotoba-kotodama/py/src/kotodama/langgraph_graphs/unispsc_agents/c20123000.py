from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    part_id: str
    load_profile: float
    inspection_result: bool
    history_log: List[str]

def validate_load_capacity(state: ProcessingState) -> ProcessingState:
    state['inspection_result'] = state['load_profile'] < 50000.0
    state['history_log'].append(f'Load validation: {state['inspection_result']}')
    return state

def route_by_inspection(state: ProcessingState) -> str:
    return 'process' if state['inspection_result'] else 'reject'

def process_bearing(state: ProcessingState) -> ProcessingState:
    state['history_log'].append('Bearing certified for industrial assembly')
    return state

builder = StateGraph(ProcessingState)
builder.add_node('validate', validate_load_capacity)
builder.add_node('process', process_bearing)
builder.add_edge('validate', 'process')
builder.add_conditional_edges('validate', route_by_inspection, {'process': 'process', 'reject': END})
builder.set_entry_point('validate')
builder.add_edge('process', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'load_profile': 0.0,
    'inspection_result': False,
    'history_log': []
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
