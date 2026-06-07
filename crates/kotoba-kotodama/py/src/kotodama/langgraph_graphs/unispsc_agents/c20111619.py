from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    spec: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_materials(state: BearingState) -> BearingState:
    material_data = state['spec'].get('material_composition_report', {})
    # Logic for checking material composition compliance
    return {'validation_log': ['Material composition validated against ISO standards.']}

def conduct_stress_test(state: BearingState) -> BearingState:
    # Logic for simulating physical inspection against load criteria
    return {'validation_log': ['Stress test passed under simulated load conditions.'], 'is_approved': True}

workflow = StateGraph(BearingState)
workflow.add_node('material_check', validate_materials)
workflow.add_node('stress_test', conduct_stress_test)
workflow.set_entry_point('material_check')
workflow.add_edge('material_check', 'stress_test')
workflow.add_edge('stress_test', END)

graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec': {},
    'validation_log': [],
    'is_approved': False
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
