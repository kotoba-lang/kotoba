from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalMaterialState(TypedDict):
    material_id: str
    compliance_checked: bool
    passed_qa: bool

def validate_porcelain(state: DentalMaterialState):
    print(f"Validating porcelain teeth: {state['material_id']}")
    return {"compliance_checked": True}

def perform_qa(state: DentalMaterialState):
    print("Running biocompatibility and hardness testing.")
    return {"passed_qa": True}

graph = StateGraph(DentalMaterialState)
graph.add_node("validate", validate_porcelain)
graph.add_node("qa", perform_qa)
graph.set_entry_point("validate")
graph.add_edge("validate", "qa")
graph.add_edge("qa", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'compliance_checked': False,
    'passed_qa': False
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
