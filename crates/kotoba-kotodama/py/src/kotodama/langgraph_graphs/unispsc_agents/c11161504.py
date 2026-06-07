from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CeramicState(TypedDict):
    material_id: str
    purity: float
    particle_distribution: dict
    validation_log: List[str]
    approved: bool

def validate_material(state: CeramicState) -> CeramicState:
    log = state.get("validation_log", [])
    if state["purity"] >= 99.9:
        log.append("High purity validated for semiconductor grade.")
        state["approved"] = True
    else:
        log.append("Purity insufficient for target application.")
        state["approved"] = False
    state["validation_log"] = log
    return state

def perform_inspection(state: CeramicState) -> CeramicState:
    if state["approved"]:
        state["validation_log"].append("Structural inspection passed.")
    return state

graph = StateGraph(CeramicState)
graph.add_node("validate", validate_material)
graph.add_node("inspect", perform_inspection)
graph.set_entry_point("validate")
graph.add_edge("validate", "inspect")
graph.add_edge("inspect", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity': 0.0,
    'particle_distribution': {},
    'validation_log': [],
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
