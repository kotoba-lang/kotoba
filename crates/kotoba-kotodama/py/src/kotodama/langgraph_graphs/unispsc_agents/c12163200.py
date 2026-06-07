from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class SemiconductorChemState(TypedDict):
    material_id: str
    purity_validated: bool
    safety_check_passed: bool
    process_steps: Annotated[list[str], operator.add]

def validate_purity(state: SemiconductorChemState) -> SemiconductorChemState:
    print(f"Validating chemical purity for {state['material_id']}")
    return {'purity_validated': True, 'process_steps': ['purity_verification']}

def perform_safety_review(state: SemiconductorChemState) -> SemiconductorChemState:
    print(f"Performing safety review for {state['material_id']}")
    return {'safety_check_passed': True, 'process_steps': ['safety_inspection']}

graph = StateGraph(SemiconductorChemState)
graph.add_node("validate_purity", validate_purity)
graph.add_node("safety_review", perform_safety_review)
graph.set_entry_point("validate_purity")
graph.add_edge("validate_purity", "safety_review")
graph.add_edge("safety_review", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity_validated': False,
    'safety_check_passed': False,
    'process_steps': []
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
