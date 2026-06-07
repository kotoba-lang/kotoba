from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    requirements: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_specs(state: ProcurementState):
    res = "COMPLIANT" if "encryption" in state['requirements'] else "NON_COMPLIANT"
    return {'validation_results': [f"Spec verification: {res}"], 'is_compliant': res == "COMPLIANT"}

def route_procurement(state: ProcurementState):
    return "process_hardware" if state['is_compliant'] else "manual_review"

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_specs)
graph.add_node("process_hardware", lambda x: {"validation_results": ["Processing hardware order"]})
graph.add_node("manual_review", lambda x: {"validation_results": ["Escalating to manual procurement review"]})
graph.set_entry_point("validate")
graph.add_conditional_edges("validate", route_procurement)
graph.add_edge("process_hardware", END)
graph.add_edge("manual_review", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'requirements': {},
    'validation_results': [],
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
