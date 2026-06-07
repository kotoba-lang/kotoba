from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
import operator

class BariteState(TypedDict):
    purity: float
    gravity: float
    inspection_report: str
    is_approved: bool
    history: Annotated[List[str], operator.add]

def validate_quality(state: BariteState) -> BariteState:
    approved = state['purity'] >= 95.0 and state['gravity'] >= 4.2
    return {'is_approved': approved, 'history': ['Validated quality metrics']}

def perform_audit(state: BariteState) -> BariteState:
    return {'history': ['Completed technical compliance audit']}

def route_by_approval(state: BariteState) -> str:
    return 'audit' if state['is_approved'] else END

graph = StateGraph(BariteState)
graph.add_node('validate', validate_quality)
graph.add_node('audit', perform_audit)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_approval)
graph.add_edge('audit', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'gravity': 0.0,
    'inspection_report': "",
    'is_approved': False,
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
