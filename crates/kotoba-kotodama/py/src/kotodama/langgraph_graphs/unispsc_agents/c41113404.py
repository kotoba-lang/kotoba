from typing import TypedDict
from langgraph.graph import StateGraph, END

class RadiationCounterState(TypedDict):
    device_id: str
    calibration_status: bool
    sensitivity_check: float
    status: str

def validate_calibration(state: RadiationCounterState):
    return {"calibration_status": state["sensitivity_check"] > 0.95}

def perform_safety_check(state: RadiationCounterState):
    return {"status": "READY" if state["calibration_status"] else "REJECTED"}

graph = StateGraph(RadiationCounterState)
graph.add_node("calibrate", validate_calibration)
graph.add_node("safety", perform_safety_check)
graph.add_edge("calibrate", "safety")
graph.add_edge("safety", END)
graph.set_entry_point("calibrate")
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'device_id': "",
    'calibration_status': False,
    'sensitivity_check': 0.0,
    'status': ""
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
