from typing import TypedDict
from langgraph.graph import StateGraph, END

class BronzeTubeState(TypedDict):
    material_spec: str
    dimensions: dict
    compliance_check: bool

def validate_material(state: BronzeTubeState):
    # Simulate alloy chemical composition verification
    valid = "C51000" in state['material_spec']
    return {'compliance_check': valid}

def structural_analysis(state: BronzeTubeState):
    # Perform dimensional validation for wall thickness
    return {'compliance_check': state['dimensions'].get('thickness', 0) > 0}

graph = StateGraph(BronzeTubeState)
graph.add_node("validate_material", validate_material)
graph.add_node("structural_analysis", structural_analysis)
graph.set_entry_point("validate_material")
graph.add_edge("validate_material", "structural_analysis")
graph.add_edge("structural_analysis", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_spec': "",
    'dimensions': {},
    'compliance_check': False
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
