from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class LubricantState(TypedDict):
    commodity_code: str
    spec_data: dict
    validation_log: List[str]
    is_compliant: bool

def validate_chemistry(state: LubricantState) -> LubricantState:
    spec = state['spec_data']
    if spec.get('flash_point', 0) > 100:
        state['validation_log'].append('Flash point safe')
        state['is_compliant'] = True
    else:
        state['validation_log'].append('Safety violation')
        state['is_compliant'] = False
    return state

def check_dual_use(state: LubricantState) -> LubricantState:
    if state.get('is_compliant'):
        state['validation_log'].append('Dual-use screening passed')
    return state

graph = StateGraph(LubricantState)
graph.add_node('chemistry', validate_chemistry)
graph.add_node('export', check_dual_use)
graph.add_edge('chemistry', 'export')
graph.add_edge('export', END)
graph.set_entry_point('chemistry')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'spec_data': {},
    'validation_log': [],
    'is_compliant': False
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
