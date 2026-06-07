from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    catalyst_id: str
    purity_level: float
    safety_check_passed: bool
    validation_log: Annotated[Sequence[str], operator.add]

def validate_purity(state: CatalystState) -> CatalystState:
    if state['purity_level'] < 0.98:
        return {'validation_log': ['Purity level below standard: 98% required.']}
    return {'safety_check_passed': True, 'validation_log': ['Purity validation passed.']}

def safety_compliance_check(state: CatalystState) -> CatalystState:
    if not state.get('safety_check_passed'):
        return {'validation_log': ['Compliance check failed: Safety protocols missing.']}
    return {'validation_log': ['Safety protocols verified.']}

def build_graph():
    graph = StateGraph(CatalystState)
    graph.add_node('validate_purity', validate_purity)
    graph.add_node('safety_compliance', safety_compliance_check)
    graph.set_entry_point('validate_purity')
    graph.add_edge('validate_purity', 'safety_compliance')
    graph.add_edge('safety_compliance', END)
    return graph.compile()

graph = build_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'catalyst_id': "",
    'purity_level': 0.0,
    'safety_check_passed': False,
    'validation_log': []
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
