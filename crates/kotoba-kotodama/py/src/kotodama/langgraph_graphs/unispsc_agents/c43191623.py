from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PeriphState(TypedDict):
    device_id: str
    spec_requirements: List[str]
    validation_log: List[str]
    status: str

def validate_compatibility(state: PeriphState):
    log = f"Validating device {state['device_id']} against specs: {state['spec_requirements']}"
    return {"validation_log": [log], "status": "COMPATIBILITY_CHECKED"}

def verify_driver_integrity(state: PeriphState):
    log = "Verifying driver signature and hardware compatibility."
    return {"validation_log": state.get("validation_log", []) + [log], "status": "VERIFIED"}

builder = StateGraph(PeriphState)
builder.add_node("check", validate_compatibility)
builder.add_node("driver", verify_driver_integrity)
builder.set_entry_point("check")
builder.add_edge("check", "driver")
builder.add_edge("driver", END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'device_id': "",
    'spec_requirements': [],
    'validation_log': [],
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
