from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SpillKitState(TypedDict):
    kit_id: str
    contents: List[str]
    compliance_status: bool
    is_hazardous_material: bool

def validate_compliance(state: SpillKitState):
    # Simulate regulatory validation logic
    state['compliance_status'] = len(state['contents']) > 0
    return state

def check_hazmat(state: SpillKitState):
    state['is_hazardous_material'] = True # Default logic for spill kits
    return state

workflow = StateGraph(SpillKitState)
workflow.add_node('validate', validate_compliance)
workflow.add_node('hazmat_check', check_hazmat)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'hazmat_check')
workflow.add_edge('hazmat_check', END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'kit_id': "",
    'contents': [],
    'compliance_status': False,
    'is_hazardous_material': False
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
