from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    reagent_id: str
    purity_check: bool
    safety_clearance: bool
    analysis_workflow: List[str]

def validate_purity(state: ReagentState) -> ReagentState:
    # Simulate high-precision purity verification logic
    state['purity_check'] = True
    return state

def run_safety_protocol(state: ReagentState) -> ReagentState:
    # Simulate dangerous goods compliance check
    state['safety_clearance'] = True
    state['analysis_workflow'].append('Safety-Checked')
    return state

def define_analysis(state: ReagentState) -> ReagentState:
    state['analysis_workflow'].append('Composition-Analysis')
    return state

graph = StateGraph(ReagentState)
graph.add_node('verify_purity', validate_purity)
graph.add_node('safety_check', run_safety_protocol)
graph.add_node('analysis', define_analysis)
graph.add_edge('verify_purity', 'safety_check')
graph.add_edge('safety_check', 'analysis')
graph.add_edge('analysis', END)
graph.set_entry_point('verify_purity')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'reagent_id': "",
    'purity_check': False,
    'safety_clearance': False,
    'analysis_workflow': []
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
