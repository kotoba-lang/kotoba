from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    commodity_id: str
    purity_check_passed: bool
    safety_clearance: bool
    hazmat_approved: bool
    history: List[str]

def validate_purity(state: ChemicalProcurementState):
    # Simulate chemical analysis logic
    return {"purity_check_passed": True, "history": state["history"] + ["Purity validated"]}

def perform_safety_check(state: ChemicalProcurementState):
    # Simulate regulatory safety assessment
    return {"safety_clearance": True, "history": state["history"] + ["Safety clearance passed"]}

def hazmat_logistics_review(state: ChemicalProcurementState):
    # Simulate dangerous goods compliance verification
    return {"hazmat_approved": True, "history": state["history"] + ["Hazmat logistics approved"]}

graph = StateGraph(ChemicalProcurementState)
graph.add_node("validate_purity", validate_purity)
graph.add_node("safety_check", perform_safety_check)
graph.add_node("hazmat_review", hazmat_logistics_review)

graph.set_entry_point("validate_purity")
graph.add_edge("validate_purity", "safety_check")
graph.add_edge("safety_check", "hazmat_review")
graph.add_edge("hazmat_review", END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_id': "",
    'purity_check_passed': False,
    'safety_clearance': False,
    'hazmat_approved': False,
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
