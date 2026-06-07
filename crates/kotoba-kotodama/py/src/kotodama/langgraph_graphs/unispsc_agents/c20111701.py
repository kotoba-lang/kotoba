from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PumpProcurementState(TypedDict):
    commodity_code: str
    pressure_spec: float
    flow_rate: float
    is_validated: bool
    validation_log: List[str]

def validate_specs(state: PumpProcurementState) -> PumpProcurementState:
    log = state.get("validation_log", [])
    if state["pressure_spec"] > 70.0:
        log.append("High pressure rating requires extra scrutiny.")
    state["is_validated"] = True
    state["validation_log"] = log
    return state

def check_export_control(state: PumpProcurementState) -> PumpProcurementState:
    if state["pressure_spec"] > 21.0:
        state["validation_log"].append("Potential Dual-Use Export Control flagged.")
    return state

graph = StateGraph(PumpProcurementState)
graph.add_node("validate_specs", validate_specs)
graph.add_node("export_check", check_export_control)
graph.set_entry_point("validate_specs")
graph.add_edge("validate_specs", "export_check")
graph.add_edge("export_check", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'pressure_spec': 0.0,
    'flow_rate': 0.0,
    'is_validated': False,
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
