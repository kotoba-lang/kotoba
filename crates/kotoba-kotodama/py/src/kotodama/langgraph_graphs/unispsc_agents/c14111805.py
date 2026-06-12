from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class OfficeLabelState(TypedDict):
    label_id: str
    spec_verified: bool
    validation_log: list[str]

def validate_label_spec(state: OfficeLabelState):
    log = state.get("validation_log", [])
    log.append(f"Validating specification for label: {state['label_id']}")
    return {"spec_verified": True, "validation_log": log}

def process_procurement_workflow(state: OfficeLabelState):
    log = state.get("validation_log", [])
    log.append("Proceeding to inventory allocation.")
    return {"validation_log": log}

graph = StateGraph(OfficeLabelState)
graph.add_node("validate", validate_label_spec)
graph.add_node("process", process_procurement_workflow)
graph.add_edge("validate", "process")
graph.add_edge("process", END)
graph.set_entry_point("validate")
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'label_id': "",
    'spec_verified': False,
    'validation_log': []
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
