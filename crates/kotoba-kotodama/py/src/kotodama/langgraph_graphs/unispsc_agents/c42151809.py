from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class DentalSupplyState(TypedDict):
    item_name: str
    specs: dict
    approved: bool
    compliance_checks: List[str]

def validate_biocompatibility(state: DentalSupplyState):
    checks = state.get('compliance_checks', [])
    if 'iso_10993' in state['specs'].get('certifications', []):
        checks.append('Biocompatibility Verified')
    return {'compliance_checks': checks}

def inspect_material(state: DentalSupplyState):
    is_sterile = state['specs'].get('sterility') == 'high_grade'
    return {'approved': is_sterile}

graph = StateGraph(DentalSupplyState)
graph.add_node('validate', validate_biocompatibility)
graph.add_node('inspect', inspect_material)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'item_name': "",
    'specs': {},
    'approved': False,
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
