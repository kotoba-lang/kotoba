from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    purity_level: float
    temp_log: list
    is_compliant: bool

def validate_purity(state: ProcurementState):
    threshold = 99.5
    return {"is_compliant": state["purity_level"] >= threshold}

def check_gdp_compliance(state: ProcurementState):
    return {"is_compliant": state["is_compliant"] and all(t < 25 for t in state["temp_log"])}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_purity)
graph.add_node("gdp_check", check_gdp_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "gdp_check")
graph.add_edge("gdp_check", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'purity_level': 0.0,
    'temp_log': [],
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
