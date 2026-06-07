from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BerylliumForgeState(TypedDict):
    spec_data: dict
    validation_errors: List[str]
    certification_passed: bool

def validate_aerospace_specs(state: BerylliumForgeState):
    errors = []
    if "grade" not in state["spec_data"]: errors.append("Missing material grade")
    if not state["spec_data"].get("is_toxic_compliant", False): errors.append("Toxicity safety missing")
    return {"validation_errors": errors, "certification_passed": len(errors) == 0}

def export_review(state: BerylliumForgeState):
    print("Triggering dual-use export control review workflow...")
    return {"certification_passed": state["certification_passed"]}

graph = StateGraph(BerylliumForgeState)
graph.add_node("validate", validate_aerospace_specs)
graph.add_node("export_compliance", export_review)
graph.set_entry_point("validate")
graph.add_edge("validate", "export_compliance")
graph.add_edge("export_compliance", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_errors': [],
    'certification_passed': False
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
