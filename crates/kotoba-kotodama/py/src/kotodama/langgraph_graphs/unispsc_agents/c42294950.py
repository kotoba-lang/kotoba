from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    tool_id: str
    quality_check_passed: bool
    sterilization_validated: bool

def validate_tool_integrity(state: ToolState) -> ToolState:
    print(f'Validating integrity of tool: {state["tool_id"]}')
    return {**state, "quality_check_passed": True}

def verify_sterilization(state: ToolState) -> ToolState:
    print(f'Verifying sterilization logs for: {state["tool_id"]}')
    return {**state, "sterilization_validated": True}

graph = StateGraph(ToolState)
graph.add_node("integrity_check", validate_tool_integrity)
graph.add_node("sterilization_check", verify_sterilization)
graph.set_entry_point("integrity_check")
graph.add_edge("integrity_check", "sterilization_check")
graph.add_edge("sterilization_check", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'tool_id': "",
    'quality_check_passed': False,
    'sterilization_validated': False
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
