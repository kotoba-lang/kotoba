from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AluminumProcurementState(TypedDict):
    material_id: str
    purity: float
    composition: dict
    approved: bool
    validation_log: List[str]

def validate_material(state: AluminumProcurementState):
    log = []
    is_valid = True
    if state['purity'] < 99.7:
        log.append(f'Purity {state["purity"]} below 99.7% threshold.')
        is_valid = False
    return {'approved': is_valid, 'validation_log': log}

def prepare_shipping(state: AluminumProcurementState):
    return {'validation_log': state['validation_log'] + ['Logistics: Heat treatment verified.']}

def build_graph():
    workflow = StateGraph(AluminumProcurementState)
    workflow.add_node('validate', validate_material)
    workflow.add_node('shipping', prepare_shipping)
    workflow.set_entry_point('validate')
    workflow.add_edge('validate', 'shipping')
    workflow.add_edge('shipping', END)
    return workflow.compile()

graph = build_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity': 0.0,
    'composition': {},
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
