from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RoboticState(TypedDict):
    part_id: str
    precision_score: float
    inspection_status: str
    workflow_logs: List[str]

def validate_precision(state: RoboticState) -> RoboticState:
    state['workflow_logs'].append('Validating precision criteria...')
    state['precision_score'] = 0.98
    state['inspection_status'] = 'COMPLETED' if state['precision_score'] > 0.95 else 'REJECTED'
    return state

def assembly_process(state: RoboticState) -> RoboticState:
    state['workflow_logs'].append('Executing precision assembly step...')
    return state

graph = StateGraph(RoboticState)
graph.add_node('validate', validate_precision)
graph.add_node('assemble', assembly_process)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', lambda s: 'assemble' if s['inspection_status'] == 'COMPLETED' else END)
graph.add_edge('assemble', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'precision_score': 0.0,
    'inspection_status': "",
    'workflow_logs': []
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
