from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SeedProcurementState(TypedDict):
    seed_code: str
    germination_rate: float
    quarantine_status: str
    approved: bool

def validate_purity(state: SeedProcurementState) -> SeedProcurementState:
    # Logic for purity validation
    state['approved'] = state['germination_rate'] > 0.85
    return state

def quarantine_check(state: SeedProcurementState) -> SeedProcurementState:
    # Logic for quarantine documentation check
    state['quarantine_status'] = 'CLEARED' if state.get('quarantine_status') == 'PASSED' else 'PENDING'
    return state

workflow = StateGraph(SeedProcurementState)
workflow.add_node('purity_check', validate_purity)
workflow.add_node('quarantine', quarantine_check)
workflow.set_entry_point('purity_check')
workflow.add_edge('purity_check', 'quarantine')
workflow.add_edge('quarantine', END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'seed_code': "",
    'germination_rate': 0.0,
    'quarantine_status': "",
    'approved': False
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
