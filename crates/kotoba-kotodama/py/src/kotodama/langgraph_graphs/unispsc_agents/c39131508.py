from typing import TypedDict
from langgraph.graph import StateGraph, END

class WireMarkerState(TypedDict):
    marker_type: str
    material_spec: str
    is_compliant: bool

def validate_materials(state: WireMarkerState):
    # Business logic for verifying if adhesive meets industrial standards
    state['is_compliant'] = 'industrial_grade' in state['material_spec']
    return state

def check_dispenser_fit(state: WireMarkerState):
    # Logic to verify roll compatibility with existing inventory
    return {'is_compliant': state['is_compliant']}

workflow = StateGraph(WireMarkerState)
workflow.add_node('validate', validate_materials)
workflow.add_node('fit_check', check_dispenser_fit)
workflow.add_edge('validate', 'fit_check')
workflow.add_edge('fit_check', END)
workflow.set_entry_point('validate')
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'marker_type': "",
    'material_spec': "",
    'is_compliant': False
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
