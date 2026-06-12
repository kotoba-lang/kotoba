from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BakeryState(TypedDict):
    product_info: dict
    compliance_ok: bool
    delivery_notes: List[str]

def validate_perishables(state: BakeryState):
    shelf_life = state['product_info'].get('shelf_life', 0)
    if shelf_life < 3:
        return {'compliance_ok': False, 'delivery_notes': ['Short shelf life risk']}
    return {'compliance_ok': True, 'delivery_notes': ['Shelf life verified']}

def check_certification(state: BakeryState):
    certs = state['product_info'].get('certs', [])
    if 'HACCP' not in certs:
        return {'compliance_ok': False, 'delivery_notes': ['Missing HACCP certification']}
    return {'compliance_ok': True}

graph = StateGraph(BakeryState)
graph.add_node('validate_shelf_life', validate_perishables)
graph.add_node('verify_certs', check_certification)
graph.set_entry_point('validate_shelf_life')
graph.add_edge('validate_shelf_life', 'verify_certs')
graph.add_edge('verify_certs', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_info': {},
    'compliance_ok': False,
    'delivery_notes': []
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
