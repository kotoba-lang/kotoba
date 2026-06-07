from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class ProcurementState(TypedDict):
    commodity_id: str
    spec_data: dict
    validation_results: Annotated[list, operator.add]
    is_compliant: bool

def validate_specs(state: ProcurementState):
    specs = state.get("spec_data", {})
    # Logic to validate specialized oil/drilling equipment standards
    results = []
    if "explosion_proof_rating" not in specs:
        results.append("Missing explosion proof rating")
    return {"validation_results": results, "is_compliant": len(results) == 0}

def route_by_compliance(state: ProcurementState):
    return "compliant_path" if state["is_compliant"] else "review_path"

def log_compliant(state: ProcurementState):
    print(f"Commodity {state['commodity_id']} validated successfully.")
    return {}

def escalate_review(state: ProcurementState):
    print(f"Flagging {state['commodity_id']} for hazardous/sanctions review.")
    return {}

builder = StateGraph(ProcurementState)
builder.add_node("validate", validate_specs)
builder.add_node("compliant_path", log_compliant)
builder.add_node("review_path", escalate_review)
builder.set_entry_point("validate")
builder.add_conditional_edges("validate", route_by_compliance)
builder.add_edge("compliant_path", END)
builder.add_edge("review_path", END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_id': "",
    'spec_data': {},
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
