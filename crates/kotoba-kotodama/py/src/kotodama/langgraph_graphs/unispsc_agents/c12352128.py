from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    purity_level: float
    safety_clearance: bool
    batch_data: dict
    workflow_log: List[str]

def validate_purity(state: ChemicalState):
    is_pure = state['purity_level'] >= 0.999
    return {'safety_clearance': is_pure, 'workflow_log': state['workflow_log'] + ['Purity validation complete']}

def process_dangerous_goods(state: ChemicalState):
    return {'workflow_log': state['workflow_log'] + ['Safety protocols engaged for transport']}

def compile_graph():
    graph = StateGraph(ChemicalState)
    graph.add_node('validate_purity', validate_purity)
    graph.add_node('process_dangerous_goods', process_dangerous_goods)
    graph.set_entry_point('validate_purity')
    graph.add_edge('validate_purity', 'process_dangerous_goods')
    graph.add_edge('process_dangerous_goods', END)
    return graph.compile()

graph = compile_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity_level': 0.0,
    'safety_clearance': False,
    'batch_data': {},
    'workflow_log': []
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
