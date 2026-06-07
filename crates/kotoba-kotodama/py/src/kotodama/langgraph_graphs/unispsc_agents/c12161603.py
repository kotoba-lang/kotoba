from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MaterialProcurementState(TypedDict):
    material_id: str
    purity: float
    specs: dict
    approved: bool
    validation_log: List[str]

def validate_material_purity(state: MaterialProcurementState):
    if state['purity'] >= 99.99:
        return {'approved': True, 'validation_log': ['Purity validated > 99.99%']}
    return {'approved': False, 'validation_log': ['Purity insufficient for high-spec manufacturing']}

def check_certification(state: MaterialProcurementState):
    if 'certification_iso9001' in state['specs']:
        return {'validation_log': state['validation_log'] + ['ISO9001 certification found']}
    return {'approved': False, 'validation_log': state['validation_log'] + ['Missing ISO9001 certification']}

graph = StateGraph(MaterialProcurementState)
graph.add_node('validate_purity', validate_material_purity)
graph.add_node('check_cert', check_certification)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_cert')
graph.add_edge('check_cert', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity': 0.0,
    'specs': {},
    'approved': False,
    'validation_log': []
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
