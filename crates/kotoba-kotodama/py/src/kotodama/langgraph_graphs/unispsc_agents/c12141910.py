from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    material_id: str
    purity: float
    process_specs: dict
    is_validated: bool
    error_logs: List[str]

def validate_catalyst_specs(state: CatalystState):
    is_valid = state['purity'] >= 99.5
    return {'is_validated': is_valid, 'error_logs': [] if is_valid else ['Purity below threshold']}

def route_by_validation(state: CatalystState):
    return 'VALID' if state['is_validated'] else 'REJECT'

def finalize_order(state: CatalystState):
    return {'material_id': state['material_id'] + '_APPROVED'}

graph = StateGraph(CatalystState)
graph.add_node('validate', validate_catalyst_specs)
graph.add_node('finalize', finalize_order)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity': 0.0,
    'process_specs': {},
    'is_validated': False,
    'error_logs': []
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
