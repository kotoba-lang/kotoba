from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MountingKitState(TypedDict):
    kit_id: str
    components: List[str]
    compliance_check: bool

def validate_components(state: MountingKitState):
    state['compliance_check'] = all(c is not None for c in state['components'])
    print(f'Validating components for kit {state['kit_id']}')
    return state

def check_inventory(state: MountingKitState):
    print('Checking inventory levels for required fasteners')
    return {'compliance_check': True}

graph = StateGraph(MountingKitState)
graph.add_node('validate', validate_components)
graph.add_node('inventory', check_inventory)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inventory')
graph.add_edge('inventory', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'kit_id': "",
    'components': [],
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
