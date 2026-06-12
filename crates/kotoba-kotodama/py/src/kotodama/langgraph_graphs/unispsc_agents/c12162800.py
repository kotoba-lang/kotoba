from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    material_id: str
    purity: float
    safety_check_passed: bool
    log: List[str]

def validate_purity(state: ChemicalState):
    if state['purity'] >= 99.9:
        state['safety_check_passed'] = True
        state['log'].append('Purity validated for industrial grade.')
    else:
        state['safety_check_passed'] = False
        state['log'].append('Purity failed inspection.')
    return state

def route_by_safety(state: ChemicalState):
    return 'process' if state['safety_check_passed'] else 'reject'

def process_chemical(state: ChemicalState):
    state['log'].append('Chemical processing in controlled environment.')
    return state

def reject_chemical(state: ChemicalState):
    state['log'].append('Chemical rejected due to safety failure.')
    return state

graph = StateGraph(ChemicalState)
graph.add_node('validate', validate_purity)
graph.add_node('process', process_chemical)
graph.add_node('reject', reject_chemical)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_safety)
graph.add_edge('process', END)
graph.add_edge('reject', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity': 0.0,
    'safety_check_passed': False,
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
