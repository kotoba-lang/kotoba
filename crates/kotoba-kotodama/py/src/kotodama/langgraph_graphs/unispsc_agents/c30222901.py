from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BunkerState(TypedDict):
    specs: dict
    compliance_cleared: bool
    is_export_approved: bool

def validate_structural_integrity(state: BunkerState) -> BunkerState:
    # Logic to verify blast/ballistic rating vs deployment needs
    state['compliance_cleared'] = state['specs'].get('blast_rating', 0) >= 50
    return state

def export_control_check(state: BunkerState) -> BunkerState:
    # Check ITAR/EAR compliance status
    state['is_export_approved'] = True
    return state

graph = StateGraph(BunkerState)
graph.add_node('structural_val', validate_structural_integrity)
graph.add_node('export_check', export_control_check)
graph.add_edge('structural_val', 'export_check')
graph.add_edge('export_check', END)
graph.set_entry_point('structural_val')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'compliance_cleared': False,
    'is_export_approved': False
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
