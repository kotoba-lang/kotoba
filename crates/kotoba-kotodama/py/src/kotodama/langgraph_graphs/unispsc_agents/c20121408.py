from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    spec: dict
    validation_results: Annotated[list[str], operator.add]
    status: str

def validate_load_capacity(state: BearingState) -> BearingState:
    spec = state['spec']
    if spec.get('load_rating_dynamic', 0) > 0:
        state['validation_results'].append('Load capacity check passed')
    else:
        state['validation_results'].append('Load capacity check failed')
    return state

def check_material_compliance(state: BearingState) -> BearingState:
    if state['spec'].get('material_grade') in ['bearing_steel', 'ceramic']:
        state['validation_results'].append('Material compliance passed')
    else:
        state['validation_results'].append('Material compliance failed')
    return state

workflow = StateGraph(BearingState)
workflow.add_node('validate_load', validate_load_capacity)
workflow.add_node('check_material', check_material_compliance)

workflow.set_entry_point('validate_load')
workflow.add_edge('validate_load', 'check_material')
workflow.add_edge('check_material', END)

graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec': {},
    'validation_results': [],
    'status': ""
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
