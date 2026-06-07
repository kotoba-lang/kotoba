from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SiliconState(TypedDict):
    purity: float
    resistivity: float
    status: str
    validation_log: List[str]

def validate_material(state: SiliconState) -> SiliconState:
    logs = state.get("validation_log", [])
    if state["purity"] < 99.9999999:
        state["status"] = "REJECTED"
        logs.append("Purity below electronic grade standards")
    else:
        state["status"] = "VALIDATED"
        logs.append("Purity check passed")
    return {"status": state["status"], "validation_log": logs}

def check_resistivity(state: SiliconState) -> SiliconState:
    logs = state.get("validation_log", [])
    if 0.01 <= state["resistivity"] <= 1000:
        logs.append("Resistivity within operating range")
    else:
        state["status"] = "REJECTED"
        logs.append("Resistivity out of tolerance")
    return {"status": state["status"], "validation_log": logs}

builder = StateGraph(SiliconState)
builder.add_node("validate", validate_material)
builder.add_node("resistivity", check_resistivity)
builder.add_edge("validate", "resistivity")
builder.add_edge("resistivity", END)
builder.set_entry_point("validate")
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'resistivity': 0.0,
    'status': "",
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
