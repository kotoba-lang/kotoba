from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SeedState(TypedDict):
    seed_id: str
    quarantine_status: bool
    germination_result: float
    inspection_passed: bool

def validate_quarantine(state: SeedState) -> SeedState:
    # Simulate strict regulatory check for agricultural seeds
    state['quarantine_status'] = True
    return state

def run_quality_check(state: SeedState) -> SeedState:
    # Simulate laboratory analysis for seed viability
    state['inspection_passed'] = state['germination_result'] > 0.85
    return state

graph = StateGraph(SeedState)
graph.add_node('validate_quarantine', validate_quarantine)
graph.add_node('run_quality_check', run_quality_check)
graph.set_entry_point('validate_quarantine')
graph.add_edge('validate_quarantine', 'run_quality_check')
graph.add_edge('run_quality_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'seed_id': "",
    'quarantine_status': False,
    'germination_result': 0.0,
    'inspection_passed': False
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
