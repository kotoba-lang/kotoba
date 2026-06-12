from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class BreedingState(TypedDict):
    spec_data: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_cleared: bool

def validate_genetic_data(state: BreedingState):
    log = "Genetic markers verified against registry." if "breed_id" in state["spec_data"] else "Genetic verification failed."
    return {"validation_logs": [log], "is_cleared": "breed_id" in state["spec_data"]}

def check_cold_chain(state: BreedingState):
    log = "Cold chain parameters validated." if state["spec_data"].get("cold_chain_compliance_report") else "Cold chain risk detected."
    return {"validation_logs": [log]}

graph = StateGraph(BreedingState)
graph.add_node("genetic_check", validate_genetic_data)
graph.add_node("cold_chain_check", check_cold_chain)
graph.add_edge("genetic_check", "cold_chain_check")
graph.add_edge("cold_chain_check", END)
graph.set_entry_point("genetic_check")
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_logs': [],
    'is_cleared': False
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
