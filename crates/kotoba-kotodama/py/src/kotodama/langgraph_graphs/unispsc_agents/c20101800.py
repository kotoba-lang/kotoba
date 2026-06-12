from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class FastenerState(TypedDict):
    part_number: str
    material_spec: str
    strength_check: bool
    compliance_report: List[str]

def validate_material(state: FastenerState) -> FastenerState:
    # Logic to verify material grade against industry standards
    state['strength_check'] = 'High-Tensile' in state['material_spec']
    state['compliance_report'].append('Material grade validated')
    return state

def generate_cert(state: FastenerState) -> FastenerState:
    if state['strength_check']:
        state['compliance_report'].append('ISO-9001 Certification Generated')
    return state

graph = StateGraph(FastenerState)
graph.add_node('validate', validate_material)
graph.add_node('certify', generate_cert)
graph.set_entry_point('validate')
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'material_spec': "",
    'strength_check': False,
    'compliance_report': []
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
