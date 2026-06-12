from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TractionState(TypedDict):
    spec_requirements: dict
    validation_passed: bool
    compliance_report: str

def validate_materials(state: TractionState):
    # Business logic for confirming medical grade compliance
    state['validation_passed'] = 'ISO-13485' in state['spec_requirements'].get('certs', [])
    return {'validation_passed': state['validation_passed']}

def generate_compliance_report(state: TractionState):
    report = "Validated" if state['validation_passed'] else "Review Needed"
    return {'compliance_report': report}

graph = StateGraph(TractionState)
graph.add_node("validate_materials", validate_materials)
graph.add_node("generate_report", generate_compliance_report)
graph.set_entry_point("validate_materials")
graph.add_edge("validate_materials", "generate_report")
graph.add_edge("generate_report", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_requirements': {},
    'validation_passed': False,
    'compliance_report': ""
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
