from typing import TypedDict
from langgraph.graph import StateGraph, END

class EduState(TypedDict):
    material_id: str
    safety_verified: bool
    age_appropriateness_checked: bool

def validate_safety(state: EduState):
    print(f"Validating safety for {state['material_id']}")
    return {"safety_verified": True}

def validate_pedagogy(state: EduState):
    print(f"Checking pedagogical alignment for {state['material_id']}")
    return {"age_appropriateness_checked": True}

workflow = StateGraph(EduState)
workflow.add_node("safety_check", validate_safety)
workflow.add_node("pedagogy_check", validate_pedagogy)
workflow.set_entry_point("safety_check")
workflow.add_edge("safety_check", "pedagogy_check")
workflow.add_edge("pedagogy_check", END)

graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'safety_verified': False,
    'age_appropriateness_checked': False
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
