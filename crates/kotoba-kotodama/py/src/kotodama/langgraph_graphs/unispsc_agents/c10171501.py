from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class FeedSupplementState(TypedDict):
    supplement_id: str
    quality_checks: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_composition(state: FeedSupplementState):
    # Simulated validation logic for animal feed supplements
    print(f"Validating composition for {state['supplement_id']}")
    return {"quality_checks": ["composition_verified"], "is_compliant": True}

def check_regulatory_status(state: FeedSupplementState):
    print(f"Checking regulatory compliance for {state['supplement_id']}")
    return {"quality_checks": ["regulatory_passed"]}

graph = StateGraph(FeedSupplementState)
graph.add_node("validate", validate_composition)
graph.add_node("regulate", check_regulatory_status)
graph.set_entry_point("validate")
graph.add_edge("validate", "regulate")
graph.add_edge("regulate", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'supplement_id': "",
    'quality_checks': [],
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
