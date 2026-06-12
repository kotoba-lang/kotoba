from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    catalyst_id: str
    purity: float
    activity_score: float
    validation_passed: bool
    log: List[str]

def validate_purity(state: CatalystState) -> CatalystState:
    state['validation_passed'] = state['purity'] >= 0.99
    state['log'].append(f'Purity check: {state["purity"]} - Status: {state["validation_passed"]}')
    return state

def evaluate_catalyst(state: CatalystState) -> CatalystState:
    if state['validation_passed'] and state['activity_score'] > 0.8:
        state['log'].append('Catalyst meets high-activity industrial specs.')
    else:
        state['log'].append('Catalyst rejected due to insufficient specs.')
    return state

def build_graph():
    workflow = StateGraph(CatalystState)
    workflow.add_node('validate', validate_purity)
    workflow.add_node('evaluate', evaluate_catalyst)
    workflow.add_edge('validate', 'evaluate')
    workflow.add_edge('evaluate', END)
    workflow.set_entry_point('validate')
    return workflow.compile()

graph = build_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'catalyst_id': "",
    'purity': 0.0,
    'activity_score': 0.0,
    'validation_passed': False,
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
