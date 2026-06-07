from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class MineralState(TypedDict):
    raw_batch: dict
    purity_validated: bool
    impurity_report: List[str]
    log: Annotated[List[str], operator.add]

def validate_chemistry(state: MineralState):
    batch = state['raw_batch']
    purity = batch.get('purity', 0)
    valid = purity > 98.0
    return {'purity_validated': valid, 'log': [f'Chemistry validated: {valid}']}

def check_impurities(state: MineralState):
    impurities = state['raw_batch'].get('impurities', [])
    issues = [i for i in impurities if i['level'] > 0.01]
    return {'impurity_report': issues, 'log': [f'Found {len(issues)} impurity concerns']}

graph = StateGraph(MineralState)
graph.add_node('chemistry', validate_chemistry)
graph.add_node('impurities', check_impurities)
graph.set_entry_point('chemistry')
graph.add_edge('chemistry', 'impurities')
graph.add_edge('impurities', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'raw_batch': {},
    'purity_validated': False,
    'impurity_report': [],
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
