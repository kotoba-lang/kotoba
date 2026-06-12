from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class LubricantState(TypedDict):
    lubricant_id: str
    viscosity: float
    temp_range: tuple
    compliance_checks: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_viscosity(state: LubricantState):
    # Business logic for viscosity validation
    is_ok = state['viscosity'] > 0
    return {'compliance_checks': ['viscosity_validated'] if is_ok else ['viscosity_failed'], 'is_approved': is_ok}

def safety_review(state: LubricantState):
    # Logic for safety review against dangerous goods threshold
    return {'compliance_checks': ['safety_reviewed']}

def build_graph():
    graph = StateGraph(LubricantState)
    graph.add_node('validate', validate_viscosity)
    graph.add_node('safety', safety_review)
    graph.set_entry_point('validate')
    graph.add_edge('validate', 'safety')
    graph.add_edge('safety', END)
    return graph.compile()

graph = build_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'lubricant_id': "",
    'viscosity': 0.0,
    'temp_range': (),
    'compliance_checks': [],
    'is_approved': False
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
