from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ZincState(TypedDict):
    purity: float
    dimensions: dict
    compliant: bool
    log: List[str]

def validate_purity(state: ZincState):
    is_pure = state['purity'] >= 99.9
    return {'compliant': is_pure, 'log': [f'Purity check: {is_pure}の結果']}

def structural_check(state: ZincState):
    valid_dim = all(val > 0 for val in state['dimensions'].values())
    return {'compliant': state['compliant'] and valid_dim, 'log': ['構造寸法検査完了']}

graph = StateGraph(ZincState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('structural_check', structural_check)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'structural_check')
graph.add_edge('structural_check', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'dimensions': {},
    'compliant': False,
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
