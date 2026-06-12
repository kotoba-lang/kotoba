from typing import TypedDict, List, Annotated
import operator
from langgraph.graph import StateGraph, END

class MineralState(TypedDict):
    batch_id: str
    purity_level: float
    compliance_checks: Annotated[List[str], operator.add]
    is_cleared: bool

def validate_purity(state: MineralState):
    cleared = state['purity_level'] >= 95.0
    return {'compliance_checks': ['purity_verified'], 'is_cleared': cleared}

def check_origin(state: MineralState):
    return {'compliance_checks': ['origin_verified']}

graph = StateGraph(MineralState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_origin', check_origin)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_origin')
graph.add_edge('check_origin', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'purity_level': 0.0,
    'compliance_checks': [],
    'is_cleared': False
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
