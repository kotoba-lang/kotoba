from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalState(TypedDict):
    device_id: str
    validation_passed: bool
    rad_compliance: bool

def validate_radiation_safety(state: DentalState) -> DentalState:
    print(f"Validating radiation compliance for unit {state['device_id']}")
    state['rad_compliance'] = True
    return state

def check_image_fidelity(state: DentalState) -> DentalState:
    print("Running image contrast and fidelity check...")
    state['validation_passed'] = True
    return state

graph = StateGraph(DentalState)
graph.add_node("radiation_check", validate_radiation_safety)
graph.add_node("fidelity_check", check_image_fidelity)
graph.set_entry_point("radiation_check")
graph.add_edge("radiation_check", "fidelity_check")
graph.add_edge("fidelity_check", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'device_id': "",
    'validation_passed': False,
    'rad_compliance': False
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
