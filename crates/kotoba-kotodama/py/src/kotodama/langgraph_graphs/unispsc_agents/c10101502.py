from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class CattleIngestState(TypedDict):
    cattle_ids: List[str]
    health_status: List[str]
    validation_errors: Annotated[List[str], operator.add]
    is_cleared: bool

def validate_health_docs(state: CattleIngestState):
    # Simulate health doc check logic
    validated = [s for s in state['health_status'] if 'certified' in s]
    errors = [s for s in state['health_status'] if 'certified' not in s]
    return {'validation_errors': errors, 'is_cleared': len(errors) == 0}

def quarantine_workflow(state: CattleIngestState):
    # Simulate quarantine processing
    print(f"Processing quarantine for: {state['cattle_ids']}")
    return {'is_cleared': state['is_cleared']}

graph = StateGraph(CattleIngestState)
graph.add_node("validate_health", validate_health_docs)
graph.add_node("quarantine", quarantine_workflow)
graph.set_entry_point("validate_health")
graph.add_edge("validate_health", "quarantine")
graph.add_edge("quarantine", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'cattle_ids': [],
    'health_status': [],
    'validation_errors': [],
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
