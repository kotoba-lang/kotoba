from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class EnvelopeProcurementState(TypedDict):
    spec_requirements: dict
    validation_logs: Annotated[List[str], add_messages]
    approved: bool

def validate_material(state: EnvelopeProcurementState) -> EnvelopeProcurementState:
    weight = state['spec_requirements'].get('material_weight_gsm', 0)
    if weight >= 80:
        state['validation_logs'].append(f'Material density {weight}gsm acceptable.')
    else:
        state['validation_logs'].append('Critical: Material too thin.')
    return state

def check_security(state: EnvelopeProcurementState) -> EnvelopeProcurementState:
    if state['spec_requirements'].get('security_tint', False):
        state['validation_logs'].append('Security tint verified.')
    state['approved'] = True
    return state

graph = StateGraph(EnvelopeProcurementState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_security', check_security)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'check_security')
graph.add_edge('check_security', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_requirements': {},
    'validation_logs': [],
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
