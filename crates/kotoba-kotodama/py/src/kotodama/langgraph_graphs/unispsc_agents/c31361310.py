from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class TitaniumState(TypedDict):
    spec_content: str
    inspection_status: str
    compliance_score: int

def validate_welding_specs(state: TitaniumState):
    # Business logic for validating ASME welding compliance
    return {"inspection_status": "Validated" if "ASME" in state["spec_content"] else "Failed"}

def check_export_controls(state: TitaniumState):
    # Business logic for dual-use criteria
    return {"compliance_score": 100 if state["inspection_status"] == "Validated" else 0}

graph = StateGraph(TitaniumState)
graph.add_node("validate_welding", validate_welding_specs)
graph.add_node("export_compliance", check_export_controls)
graph.set_entry_point("validate_welding")
graph.add_edge("validate_welding", "export_compliance")
graph.add_edge("export_compliance", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_content': "",
    'inspection_status': "",
    'compliance_score': 0
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
