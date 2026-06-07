from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AlloyState(TypedDict):
    purity: float
    strength: float
    compliant: bool
    logs: List[str]

def analyze_ingot(state: AlloyState) -> AlloyState:
    logs = state.get("logs", [])
    is_compliant = state["purity"] >= 99.9 and state["strength"] >= 450.0
    logs.append(f"Analysis complete: Compliant={is_compliant}")
    return {"compliant": is_compliant, "logs": logs}

def validate_certification(state: AlloyState) -> AlloyState:
    logs = state.get("logs", [])
    logs.append("Checking mill test certificate...")
    return {"logs": logs}

workflow = StateGraph(AlloyState)
workflow.add_node("analyze", analyze_ingot)
workflow.add_node("certify", validate_certification)
workflow.set_entry_point("analyze")
workflow.add_edge("analyze", "certify")
workflow.add_edge("certify", END)

graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'strength': 0.0,
    'compliant': False,
    'logs': []
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
