from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    assembly_id: str
    material_spec: str
    weld_integrity_score: float
    compliance_checks: List[str]

def validate_weld_integrity(state: AssemblyState):
    if state['weld_integrity_score'] < 0.95:
        return {'compliance_checks': state['compliance_checks'] + ['Weld Strength Failed']}
    return {'compliance_checks': state['compliance_checks'] + ['Weld Strength Passed']}

def check_export_control(state: AssemblyState):
    return {'compliance_checks': state['compliance_checks'] + ['Export Control Screening Complete']}

graph = StateGraph(AssemblyState)
graph.add_node('validate_weld', validate_weld_integrity)
graph.add_node('check_export', check_export_control)
graph.set_entry_point('validate_weld')
graph.add_edge('validate_weld', 'check_export')
graph.add_edge('check_export', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'assembly_id': "",
    'material_spec': "",
    'weld_integrity_score': 0.0,
    'compliance_checks': []
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
