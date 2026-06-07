from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class BookState(TypedDict):
    title: str
    specifications: dict
    approved: bool

def validate_academic_standards(state: BookState):
    # Business logic for verifying education resource alignment
    state["approved"] = "standard" in state["specifications"].get("categories", [])
    return state

def check_print_quality(state: BookState):
    # Workflow step for checking print specifications
    if state["specifications"].get("paper_gsm", 0) < 80:
        state["approved"] = False
    return state

graph = StateGraph(BookState)
graph.add_node("validate", validate_academic_standards)
graph.add_node("print_check", check_print_quality)
graph.add_edge("validate", "print_check")
graph.add_edge("print_check", END)
graph.set_entry_point("validate")

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'title': "",
    'specifications': {},
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
