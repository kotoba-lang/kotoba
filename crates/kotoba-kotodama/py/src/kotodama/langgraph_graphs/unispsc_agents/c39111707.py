from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExitLightState(TypedDict):
    spec_sheet: dict
    approved: bool

def validate_illumination(state: ExitLightState) -> ExitLightState:
    # Logic to verify lux levels against building code standards
    state['approved'] = state['spec_sheet'].get('lux', 0) >= 10
    return state

def check_battery(state: ExitLightState) -> ExitLightState:
    # Verify battery runtime requirements
    state['approved'] = state['approved'] and state['spec_sheet'].get('runtime', 0) >= 90
    return state

graph = StateGraph(ExitLightState)
graph.add_node("validate_lux", validate_illumination)
graph.add_node("validate_battery", check_battery)
graph.set_entry_point("validate_lux")
graph.add_edge("validate_lux", "validate_battery")
graph.add_edge("validate_battery", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_sheet': {},
    'approved': False
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
