from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralState(TypedDict):
    raw_batch_id: str
    purity: float
    origin: str
    compliant: bool
    history: List[str]

def validate_ore(state: MineralState):
    if state['purity'] > 0.95:
        return {'compliant': True, 'history': state['history'] + ['Purity check passed']}
    return {'compliant': False, 'history': state['history'] + ['Purity check failed']}

def route_by_compliance(state: MineralState):
    return 'process' if state['compliant'] else 'reject'

def process_ore(state: MineralState):
    return {'history': state['history'] + ['Processing through refinery queue']}

def reject_ore(state: MineralState):
    return {'history': state['history'] + ['Rejecting batch for quality variance']}

graph = StateGraph(MineralState)
graph.add_node('validate', validate_ore)
graph.add_node('process', process_ore)
graph.add_node('reject', reject_ore)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance)
graph.add_edge('process', END)
graph.add_edge('reject', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'raw_batch_id': "",
    'purity': 0.0,
    'origin': "",
    'compliant': False,
    'history': []
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
