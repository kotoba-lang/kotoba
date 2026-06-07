from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PackagingState(TypedDict):
    dimensions: dict
    material_specs: dict
    is_compliant: bool

def validate_box_specs(state: PackagingState):
    # Business logic for confirming box structural rigidity
    required_keys = ['width', 'height', 'depth']
    state['is_compliant'] = all(k in state['dimensions'] for k in required_keys)
    return state

def run_compliance_check(state: PackagingState):
    # Simulates verification of material standards
    print(f'Checking compliance: {state['is_compliant']}')
    return 'end'

workflow = StateGraph(PackagingState)
workflow.add_node('validate', validate_box_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)

graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'dimensions': {},
    'material_specs': {},
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
