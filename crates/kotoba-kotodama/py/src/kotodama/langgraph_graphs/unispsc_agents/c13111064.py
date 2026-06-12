from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SiCPowderState(TypedDict):
    purity: float
    particle_size: float
    compliance_checks: List[str]
    status: str

def validate_purity(state: SiCPowderState):
    if state['purity'] >= 99.9:
        return {'status': 'High Purity Validated', 'compliance_checks': state['compliance_checks'] + ['purity_ok']}
    return {'status': 'Failed: Low Purity', 'compliance_checks': state['compliance_checks'] + ['purity_failed']}

def process_material(state: SiCPowderState):
    return {'status': 'Processing for Semiconductor Grade', 'compliance_checks': state['compliance_checks'] + ['processing_started']}

graph = StateGraph(SiCPowderState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('process_material', process_material)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'process_material')
graph.add_edge('process_material', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'purity': 0.0,
    'particle_size': 0.0,
    'compliance_checks': [],
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
